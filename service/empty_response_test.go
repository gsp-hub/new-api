package service

import (
	"errors"
	"net/http/httptest"
	"testing"

	"github.com/QuantumNous/new-api/relaykit/dto"
	"github.com/QuantumNous/new-api/relaykit/types"
	"github.com/QuantumNous/new-api/setting/operation_setting"
	"github.com/gin-gonic/gin"
)

func chatResponseWithChoice(content any, reasoning string, finishReason string) *dto.OpenAITextResponse {
	return &dto.OpenAITextResponse{
		Choices: []dto.OpenAITextResponseChoice{
			{
				Index: 0,
				Message: dto.Message{
					Role:             "assistant",
					Content:          content,
					ReasoningContent: &reasoning,
				},
				FinishReason: finishReason,
			},
		},
	}
}

func TestIsEmptyChatResponse(t *testing.T) {
	reasoningText := "thinking..."
	tests := []struct {
		name string
		resp *dto.OpenAITextResponse
		want bool
	}{
		{
			name: "nil response is not treated as empty",
			resp: nil,
			want: false,
		},
		{
			name: "no choices at all is empty",
			resp: &dto.OpenAITextResponse{},
			want: true,
		},
		{
			name: "normal content is not empty",
			resp: chatResponseWithChoice("hello", "", "stop"),
			want: false,
		},
		{
			name: "empty content with stop finish reason is empty",
			resp: chatResponseWithChoice("", "", "stop"),
			want: true,
		},
		{
			name: "whitespace only content is empty",
			resp: chatResponseWithChoice("   \n\t ", "", ""),
			want: true,
		},
		{
			name: "reasoning only is not empty",
			resp: &dto.OpenAITextResponse{Choices: []dto.OpenAITextResponseChoice{{
				Message: dto.Message{Role: "assistant", Content: "", ReasoningContent: &reasoningText},
			}}},
			want: false,
		},
		{
			name: "budget burned on reasoning (finish_reason=length, no content) is empty",
			resp: chatResponseWithChoice("", "", "length"),
			want: true,
		},
		{
			name: "budget burned on reasoning with exposed thinking is still empty",
			resp: &dto.OpenAITextResponse{Choices: []dto.OpenAITextResponseChoice{{
				Message:      dto.Message{Role: "assistant", Content: "", ReasoningContent: &reasoningText},
				FinishReason: "length",
			}}},
			want: true,
		},
		{
			name: "normal truncation (finish_reason=length with partial content) is not empty",
			resp: chatResponseWithChoice("partial ans", "", "length"),
			want: false,
		},
		{
			name: "content filtered is not empty",
			resp: chatResponseWithChoice("", "", "content_filter"),
			want: false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := IsEmptyChatResponse(tt.resp); got != tt.want {
				t.Fatalf("IsEmptyChatResponse() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestNewEmptyResponseErrorIsRetryable(t *testing.T) {
	err := NewEmptyResponseError(7, "gpt-5.1-sol")
	if err == nil {
		t.Fatal("expected non-nil error")
	}
	if err.StatusCode != 502 {
		t.Fatalf("expected status 502 so that retry rules match, got %d", err.StatusCode)
	}
	if err.GetErrorCode() != types.ErrorCodeEmptyResponse {
		t.Fatalf("expected error code %s, got %s", types.ErrorCodeEmptyResponse, err.GetErrorCode())
	}
	if !IsEmptyResponseError(err) {
		t.Fatal("IsEmptyResponseError should report true")
	}
	if IsEmptyResponseError(nil) {
		t.Fatal("nil error must not be reported as empty response")
	}
}

func TestRecordEmptyResponseWindowAndReset(t *testing.T) {
	const channelId = 9001
	ResetEmptyResponse(channelId)

	previous := operation_setting.EmptyResponseWindowSeconds
	operation_setting.EmptyResponseWindowSeconds = 600
	defer func() { operation_setting.EmptyResponseWindowSeconds = previous }()

	if got := RecordEmptyResponse(channelId); got != 1 {
		t.Fatalf("first record = %d, want 1", got)
	}
	if got := RecordEmptyResponse(channelId); got != 2 {
		t.Fatalf("second record = %d, want 2", got)
	}
	ResetEmptyResponse(channelId)
	if got := RecordEmptyResponse(channelId); got != 1 {
		t.Fatalf("after reset = %d, want 1", got)
	}

	// 无效渠道号不计数
	if got := RecordEmptyResponse(0); got != 0 {
		t.Fatalf("channel 0 should not be counted, got %d", got)
	}
}

func TestHandleEmptyResponseFailureResetsOnOtherErrors(t *testing.T) {
	const channelId = 9002
	RecordEmptyResponse(channelId)
	RecordEmptyResponse(channelId)

	c, _ := gin.CreateTestContext(httptest.NewRecorder())
	otherErr := types.NewOpenAIError(errors.New("upstream boom"), types.ErrorCodeBadResponseBody, 500)
	HandleEmptyResponseFailure(c, *types.NewChannelError(channelId, 1, "test", false, "", false), otherErr)

	// 非空响应错误应把计数清零
	if got := RecordEmptyResponse(channelId); got != 1 {
		t.Fatalf("counter should be reset by non-empty error, got %d", got)
	}
	ResetEmptyResponse(channelId)
}

func TestHandleEmptyResponseFailureDedupesWithinOneRequest(t *testing.T) {
	const channelId = 9003
	ResetEmptyResponse(channelId)
	previous := operation_setting.EmptyResponseDisableThreshold
	operation_setting.EmptyResponseDisableThreshold = 100 // 本用例只验证计数，不触发禁用
	operation_setting.EmptyResponseWindowSeconds = 600
	defer func() {
		operation_setting.EmptyResponseDisableThreshold = previous
		ResetEmptyResponse(channelId)
	}()

	// 同一个 gin.Context 内对同一渠道连续失败 3 次（模拟一次请求内的多次重试）
	c, _ := gin.CreateTestContext(httptest.NewRecorder())
	emptyErr := NewEmptyResponseError(channelId, "m")
	channelError := *types.NewChannelError(channelId, 1, "test", false, "", false)
	for i := 0; i < 3; i++ {
		HandleEmptyResponseFailure(c, channelError, emptyErr)
	}
	if got := peekEmptyResponseCount(channelId); got != 1 {
		t.Fatalf("3 failures in one request should count once, got %d", got)
	}

	// 新的请求（新的 Context）应再计一次
	c2, _ := gin.CreateTestContext(httptest.NewRecorder())
	HandleEmptyResponseFailure(c2, channelError, emptyErr)
	if got := peekEmptyResponseCount(channelId); got != 2 {
		t.Fatalf("second request should count again, got %d", got)
	}
}

// peekEmptyResponseCount 只读地查看当前计数，不改变计数（测试用）。
func peekEmptyResponseCount(channelId int) int {
	value, ok := emptyResponseStates.Load(channelId)
	if !ok {
		return 0
	}
	return value.(*emptyResponseState).Count
}
