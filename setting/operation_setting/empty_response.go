package operation_setting

// 空响应（Empty Response）拦截配置。
//
// 背景：部分 OpenAI 兼容上游在额度耗尽、内部异常、网关截断等情况下会返回
// HTTP 200 但正文为空（choices 为空数组，或 choices 内 content 为空字符串）。
// new-api 默认会把它当作成功响应透传给客户端并正常计费，客户端表现为
// 「模型不回答」或「返回空」，且无法重试到其它渠道。
//
// 开启本组配置后，此类响应会被转换为可重试的 502（error_code=empty_response），
// 由 new-api 现有的重试链路自动切换到其它渠道；同一渠道连续出现空响应达到
// 阈值后会被自动禁用，避免持续把流量打到坏渠道上。
var (
	// EmptyResponseGuardEnabled 是否开启空响应拦截
	EmptyResponseGuardEnabled = true
	// EmptyResponseDisableThreshold 同一渠道「连续」空响应达到该次数后自动禁用渠道，
	// <= 0 表示只重试、不自动禁用。
	//
	// 默认值定得较高（20），依据 136 生产真实流量（2026-10-30，近 2 天 6.5 万次请求）：
	//   - 空响应几乎全部集中在 gpt/codex 家族：gpt-6-sol 2.3% / gpt-6.1-sol 3.9% /
	//     gpt-6-astra 4.8%；glm 与 deepseek 接近 0%
	//   - 三个 CPA 池的空响应率分别是 1.9% / 2.0% / 3.1%，**同时受影响、同时爆发**
	//     （按小时看，07:00 那波三池分别是 25 / 31 / 32 次）
	//
	// 结论：这是上游模型家族的固有行为，不是「某个渠道坏了」。按渠道熔断在阈值较低时
	// 会把三个池一起禁用，直接造成全站不可用。因此阈值只用于识别「彻底坏掉」的渠道
	// （100% 空响应才会连续累积到 20），正常波动交给重试兜底。
	EmptyResponseDisableThreshold = 20
	// EmptyResponseWindowSeconds 连续空响应计数的时间窗口（秒），
	// 距上次空响应超过该时长则计数重新开始，避免低频渠道的历史计数一直累积
	EmptyResponseWindowSeconds = 600
)
