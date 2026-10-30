# 本 fork 相对上游的改动

上游：`QuantumNous/new-api`（跟踪 `main`）
本 fork：`gsp-hub/new-api`

用途：把 new-api 作为对内 + 对外的统一模型网关，优先保证「上游异常时客户端不会拿到空回答」。
以下改动都是**内核可靠性**层面，与充值/支付无关（那部分将放在独立分支）。

## 改动清单

### 1. 空响应拦截（新文件 + 注入点）

上游行为：上游返回 HTTP 200 但正文为空（`choices: []`，或 `content: ""`）时，
new-api 当作成功响应透传并照常计费，客户端表现为「模型不回答」，且不会重试。

改动后：视为上游失败，转成 **502 + `error_code=empty_response`**，交给重试链路切渠道。

- 新增 `setting/operation_setting/empty_response.go`：三个可配置开关
  - `EmptyResponseGuardEnabled`（默认 true）
  - `EmptyResponseDisableThreshold`（默认 3，<=0 表示只重试不禁用）
  - `EmptyResponseWindowSeconds`（默认 600）
- 新增 `service/empty_response.go`：判定逻辑、连续计数、熔断
- 注入点：
  - `relay/channel/openai/relay-openai.go` `OpenaiHandler`（非流式）
  - 同文件 `OaiStreamHandler`（流式）
- `service/relay_error.go` `ProcessChannelError`：失败后累计连续空响应次数，达阈值自动禁用渠道
- `model/option.go`：把三个开关注册进 OptionMap，可通过 `/api/option/` 在线调整

### 2. 流式空响应的安全性约束

流式无法像非流式那样自由重试：一旦已经往客户端写过字节（例如 keepalive ping），
重试会把两段流叠加，客户端解析会乱。

因此流式分支的处理是：
- 整个流既无正文、也无思维链、也无 tool_calls 且 completion_tokens=0，且**尚未写过任何字节** → 返回可重试错误
- 若已写过字节 → 只记录日志与渠道健康度，不重试

### 3. 默认开启重试

上游 `common/constants.go` 中 `RetryTimes = 0`，即**默认完全不重试**。
对网关来说这不可接受（单渠道抖动直接暴露给客户端）。

改为 `RetryTimes = 2`。注意：只在全新数据库生效，已有库以数据库内设置为准。

## 判定边界（重要，避免误杀）

以下情况**不算**空响应，不会触发重试与熔断：

- `finish_reason=length`：`max_tokens` 被耗尽（推理模型常把预算花在思维链上）
- `finish_reason=content_filter`：被上游内容审核拦截
- 存在 `tool_calls`：纯工具调用回复
- 有 `reasoning_content`：思考内容非空

## 升级上游的操作顺序

```bash
cd new-api
git fetch upstream
git checkout main
git merge upstream/main        # 冲突大概率集中在 relay-openai.go 的注入点
git checkout -b feat/xxx
```

冲突排查重点：`relay/channel/openai/relay-openai.go` 的两个注入点，
以及 `service/relay_error.go` 里 `ProcessChannelError` 的那一行调用。

改动全部集中在新文件里，注入点只有 3 处，升级成本可控。
