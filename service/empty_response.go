package service

import (
	"fmt"
	"net/http"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/QuantumNous/new-api/common"
	"github.com/QuantumNous/new-api/constant"
	"github.com/QuantumNous/new-api/model"
	"github.com/QuantumNous/new-api/relaykit/dto"
	"github.com/QuantumNous/new-api/relaykit/types"
	"github.com/QuantumNous/new-api/setting/operation_setting"
	"github.com/gin-gonic/gin"
)

// emptyResponseState 记录单个渠道的连续空响应次数。
type emptyResponseState struct {
	Count  int
	LastAt time.Time
}

var (
	emptyResponseStates sync.Map // channelID(int) -> *emptyResponseState
	emptyResponseMutex  sync.Mutex

	// 全局空响应计量，用于观察整体水位（不参与熔断决策）
	emptyResponseTotal  atomic.Int64
	emptyResponseByChan sync.Map // channelID(int) -> *atomic.Int64
)

// EmptyResponseSnapshot 返回累计空响应数与按渠道分布，供监控/排障读取。
func EmptyResponseSnapshot() (total int64, byChannel map[int]int64) {
	total = emptyResponseTotal.Load()
	byChannel = make(map[int]int64)
	emptyResponseByChan.Range(func(key, value any) bool {
		byChannel[key.(int)] = value.(*atomic.Int64).Load()
		return true
	})
	return total, byChannel
}

func countEmptyResponse(channelId int) {
	emptyResponseTotal.Add(1)
	if channelId <= 0 {
		return
	}
	value, ok := emptyResponseByChan.Load(channelId)
	if !ok {
		value, _ = emptyResponseByChan.LoadOrStore(channelId, new(atomic.Int64))
	}
	value.(*atomic.Int64).Add(1)
}

// IsEmptyChatResponse 判断一个非流式 chat completion 响应是否为「空响应」。
//
// 判定为空：没有任何 choice，或所有 choice 既没有正文、也没有思维链、
// 也没有工具调用，且结束原因不是客户端侧可控的情况。
//
// 下列情况不算空响应（属于请求侧或业务侧原因，重试无意义）：
//   - finish_reason=content_filter：被上游内容审核拦截
//   - 存在 tool_calls：纯工具调用回复
//
// 特例（2026-11-02 实测修正）：finish_reason=length 且正文为空、无工具调用时，
// 即使思维链非空也判为空响应——思考型模型把整个预算耗在思维链上，客户端
// 拿不到任何可用正文却照常计费（实测 glm-5.2 reasoning 6783 字、正文 0、
// 计费 2048 token）。换渠道重试通常能拿到正常回答。
func IsEmptyChatResponse(resp *dto.OpenAITextResponse) bool {
	if resp == nil {
		return false
	}
	if len(resp.Choices) == 0 {
		return true
	}
	for i := range resp.Choices {
		choice := &resp.Choices[i]
		message := &choice.Message
		if strings.TrimSpace(message.StringContent()) != "" {
			return false
		}
		if len(message.ParseToolCalls()) > 0 {
			return false
		}
		if choice.FinishReason == constant.FinishReasonLength {
			return true
		}
		if strings.TrimSpace(message.GetReasoningContent()) != "" {
			return false
		}
		switch choice.FinishReason {
		case constant.FinishReasonContentFilter, constant.FinishReasonToolCalls:
			return false
		}
	}
	return true
}

// NewEmptyResponseError 构造一个可重试的空响应错误。
// 状态码使用 502，使其落在默认重试状态码区间 (500-503) 内，
// 从而由 DecideRelayRetry 自动判定为需要重试。
func NewEmptyResponseError(channelId int, modelName string) *types.NewAPIError {
	return types.NewOpenAIError(
		fmt.Errorf("upstream returned an empty response (channel #%d, model %s)", channelId, modelName),
		types.ErrorCodeEmptyResponse,
		http.StatusBadGateway,
	)
}

// IsEmptyResponseError 判断错误是否为空响应错误。
func IsEmptyResponseError(err *types.NewAPIError) bool {
	if err == nil {
		return false
	}
	return err.GetErrorCode() == types.ErrorCodeEmptyResponse
}

// RecordEmptyResponse 记录一次空响应，返回该渠道在时间窗口内的连续次数。
// 超出窗口的历史计数会被重置为 1。
func RecordEmptyResponse(channelId int) int {
	if channelId <= 0 {
		return 0
	}
	window := time.Duration(operation_setting.EmptyResponseWindowSeconds) * time.Second
	if window <= 0 {
		window = 10 * time.Minute
	}

	emptyResponseMutex.Lock()
	defer emptyResponseMutex.Unlock()

	now := time.Now()
	value, ok := emptyResponseStates.Load(channelId)
	if !ok {
		emptyResponseStates.Store(channelId, &emptyResponseState{Count: 1, LastAt: now})
		return 1
	}
	state := value.(*emptyResponseState)
	if now.Sub(state.LastAt) > window {
		state.Count = 0
	}
	state.Count++
	state.LastAt = now
	return state.Count
}

// ResetEmptyResponse 清空某个渠道的连续空响应计数。
func ResetEmptyResponse(channelId int) {
	if channelId <= 0 {
		return
	}
	emptyResponseStates.Delete(channelId)
}

// emptyResponseCountedKey 用于在同一个客户端请求内对「同一渠道的空响应」去重。
// 原因：一次客户端请求可能对同一渠道重试多次（RetryTimes），
// 若每次尝试都计数，单次请求就能把阈值刷满，导致瞬时抖动直接熔断渠道。
func emptyResponseCountedKey(channelId int) string {
	return fmt.Sprintf("empty_response_counted_%d", channelId)
}

// HandleEmptyResponseFailure 在请求失败后被调用：累计空响应次数，
// 达到阈值时自动禁用渠道。非空响应类失败说明渠道仍能返回内容，计数中断。
func HandleEmptyResponseFailure(c *gin.Context, channelError types.ChannelError, err *types.NewAPIError) {
	if !IsEmptyResponseError(err) {
		ResetEmptyResponse(channelError.ChannelId)
		return
	}
	countEmptyResponse(channelError.ChannelId)
	// 同一请求内对同一渠道只计一次
	key := emptyResponseCountedKey(channelError.ChannelId)
	if c != nil {
		if _, counted := c.Get(key); counted {
			return
		}
		c.Set(key, true)
	}
	count := RecordEmptyResponse(channelError.ChannelId)
	threshold := operation_setting.EmptyResponseDisableThreshold
	if threshold <= 0 || count < threshold {
		return
	}
	ResetEmptyResponse(channelError.ChannelId)
	DisableChannel(channelError, fmt.Sprintf("consecutive empty responses: %d (threshold %d)", count, threshold))
}

// NoteEmptyResponseForStartedStream 记录一次「流已开始写客户端但内容为空」的空响应。
// 这类情况无法重试，只能累计计数，达到阈值后禁用渠道。
// 查不到渠道信息时不做自动禁用，避免误判。
func NoteEmptyResponseForStartedStream(c *gin.Context, channelId int) {
	if channelId <= 0 {
		return
	}
	channel, err := model.GetChannelById(channelId, true)
	if err != nil || channel == nil {
		common.SysLog(fmt.Sprintf("empty response guard: cannot load channel #%d, skip auto disable: %v", channelId, err))
		return
	}
	channelError := types.NewChannelError(channelId, channel.Type, channel.Name, channel.ChannelInfo.IsMultiKey, "", channel.GetAutoBan())
	HandleEmptyResponseFailure(c, *channelError, NewEmptyResponseError(channelId, channel.Name))
}
