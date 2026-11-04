package setting

import (
	"strings"
	"testing"
)

func TestGroupModelRateLimitJSONRoundTrip(t *testing.T) {
	jsonStr := `{"sub99":{"glm-5.2":150},"sub199":{"gpt-6-sol":40,"gpt-6-astra":15}}`
	if err := UpdateModelRequestRateLimitGroupModelByJSONString(jsonStr); err != nil {
		t.Fatalf("update failed: %v", err)
	}
	if got := ModelRequestRateLimitGroupModel2JSONString(); !strings.Contains(got, `"gpt-6-sol":40`) {
		t.Fatalf("round trip lost entry, got %s", got)
	}
	if count, found := GetGroupModelRateLimit("sub199", "gpt-6-astra"); !found || count != 15 {
		t.Fatalf("expected sub199/gpt-6-astra=15, got count=%d found=%v", count, found)
	}
	if _, found := GetGroupModelRateLimit("sub99", "gpt-6-sol"); found {
		t.Fatal("sub99 should not have a gpt-6-sol entry")
	}
	if _, found := GetGroupModelRateLimit("default", "glm-5.2"); found {
		t.Fatal("default group should not match")
	}
}

func TestCheckModelRequestRateLimitGroupModel(t *testing.T) {
	if err := CheckModelRequestRateLimitGroupModel(`{"g":{"m":10}}`); err != nil {
		t.Fatalf("valid json rejected: %v", err)
	}
	if err := CheckModelRequestRateLimitGroupModel(`{"g":{"m":-1}}`); err == nil {
		t.Fatal("negative count accepted")
	}
	if err := CheckModelRequestRateLimitGroupModel(`{"g":{"m":9223372036854775807}}`); err == nil {
		t.Fatal("overflow count accepted")
	}
	if err := CheckModelRequestRateLimitGroupModel(`not json`); err == nil {
		t.Fatal("invalid json accepted")
	}
}
