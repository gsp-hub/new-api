package setting

import (
	"fmt"
	"math"
	"sync"

	"github.com/QuantumNous/new-api/common"
)

// maxRateLimitDurationSeconds is the largest window the count cap is computed
// against (24h). Token-bucket capacity is count*duration; this keeps that
// product inside int64 when the window is at most a day.
const maxRateLimitDurationSeconds = 24 * 60 * 60

// maxModelRequestRateLimitCount is math.MaxInt64 / maxRateLimitDurationSeconds.
// It is the largest count that cannot overflow int64(count)*duration for a
// window of at most 24 hours.
const maxModelRequestRateLimitCount int64 = math.MaxInt64 / maxRateLimitDurationSeconds

var ModelRequestRateLimitEnabled = false
var ModelRequestRateLimitDurationMinutes = 1
var ModelRequestRateLimitCount = 0
var ModelRequestRateLimitSuccessCount = 1000
var ModelRequestRateLimitGroup = map[string][2]int{}
var ModelRequestRateLimitMutex sync.RWMutex

// ModelRequestRateLimitGroupModel caps requests per group AND per model over
// the global ModelRequestRateLimitDurationMinutes window, e.g.
// {"sub199": {"gpt-6-sol": 40, "gpt-6-astra": 15}}. Unlike the group-level
// map it counts every request (no success-only sub-counter) because it is
// enforced pre-flight in Distribute, once the model name is known.
var ModelRequestRateLimitGroupModel = map[string]map[string]int{}
var ModelRequestRateLimitGroupModelMutex sync.RWMutex

func ModelRequestRateLimitGroup2JSONString() string {
	ModelRequestRateLimitMutex.RLock()
	defer ModelRequestRateLimitMutex.RUnlock()

	jsonBytes, err := common.Marshal(ModelRequestRateLimitGroup)
	if err != nil {
		common.SysLog(common.LogText("error marshalling model ratio: %s", err.Error()))
	}
	return string(jsonBytes)
}

func UpdateModelRequestRateLimitGroupByJSONString(jsonStr string) error {
	ModelRequestRateLimitMutex.RLock()
	defer ModelRequestRateLimitMutex.RUnlock()

	ModelRequestRateLimitGroup = make(map[string][2]int)
	return common.Unmarshal([]byte(jsonStr), &ModelRequestRateLimitGroup)
}

func GetGroupRateLimit(group string) (totalCount, successCount int, found bool) {
	ModelRequestRateLimitMutex.RLock()
	defer ModelRequestRateLimitMutex.RUnlock()

	if ModelRequestRateLimitGroup == nil {
		return 0, 0, false
	}

	limits, found := ModelRequestRateLimitGroup[group]
	if !found {
		return 0, 0, false
	}
	return limits[0], limits[1], true
}

func CheckModelRequestRateLimitGroup(jsonStr string) error {
	checkModelRequestRateLimitGroup := make(map[string][2]int)
	err := common.Unmarshal([]byte(jsonStr), &checkModelRequestRateLimitGroup)
	if err != nil {
		return err
	}
	for group, limits := range checkModelRequestRateLimitGroup {
		if limits[0] < 0 || limits[1] < 1 {
			return fmt.Errorf("group %s has negative rate limit values: [%d, %d]", group, limits[0], limits[1])
		}
		if int64(limits[0]) > maxModelRequestRateLimitCount || int64(limits[1]) > maxModelRequestRateLimitCount {
			return fmt.Errorf("group %s [%d, %d] exceeds max rate limit %d", group, limits[0], limits[1], maxModelRequestRateLimitCount)
		}
	}

	return nil
}

func ModelRequestRateLimitGroupModel2JSONString() string {
	ModelRequestRateLimitGroupModelMutex.RLock()
	defer ModelRequestRateLimitGroupModelMutex.RUnlock()

	jsonBytes, err := common.Marshal(ModelRequestRateLimitGroupModel)
	if err != nil {
		common.SysLog(common.LogText("error marshalling model rate limit group model: %s", err.Error()))
	}
	return string(jsonBytes)
}

func UpdateModelRequestRateLimitGroupModelByJSONString(jsonStr string) error {
	parsed := make(map[string]map[string]int)
	if err := common.Unmarshal([]byte(jsonStr), &parsed); err != nil {
		return err
	}
	ModelRequestRateLimitGroupModelMutex.Lock()
	defer ModelRequestRateLimitGroupModelMutex.Unlock()
	ModelRequestRateLimitGroupModel = parsed
	return nil
}

func GetGroupModelRateLimit(group, modelName string) (int, bool) {
	ModelRequestRateLimitGroupModelMutex.RLock()
	defer ModelRequestRateLimitGroupModelMutex.RUnlock()

	if ModelRequestRateLimitGroupModel == nil {
		return 0, false
	}
	models, found := ModelRequestRateLimitGroupModel[group]
	if !found {
		return 0, false
	}
	count, found := models[modelName]
	return count, found
}

func CheckModelRequestRateLimitGroupModel(jsonStr string) error {
	parsed := make(map[string]map[string]int)
	if err := common.Unmarshal([]byte(jsonStr), &parsed); err != nil {
		return err
	}
	for group, models := range parsed {
		for modelName, count := range models {
			if count < 0 {
				return fmt.Errorf("group %s model %s has negative rate limit %d", group, modelName, count)
			}
			if int64(count) > maxModelRequestRateLimitCount {
				return fmt.Errorf("group %s model %s rate limit %d exceeds max %d", group, modelName, count, maxModelRequestRateLimitCount)
			}
		}
	}
	return nil
}
