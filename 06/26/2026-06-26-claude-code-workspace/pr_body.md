## 问题背景

Code review 发现评分系统存在严重的**分数稀释问题**（根因：scores 始终在 50 附近徘徊），以及多个数据层/配置层的可靠性缺陷。

## 修复清单

### Critical (评分正确性)
| # | 文件 | 问题 | 修复 |
|---|------|------|------|
| 1 | scoring/engine.py | news/catalyst/industry 无数据时注入常量 50.0，消耗 20% 权重但无区分度 | 改为 NaN + 权重自动重分配 |
| 2 | scoring/engine.py | isna().all() 只过滤全量缺失维度，部分缺失仍注入 50.0 | 增加 min_coverage=20% 阈值 |
| 3 | scoring/engine.py | fillna(50.0) 对所有维度统一填固定值 | 改用维度已有分数中位数填充 |

### High (可靠性)
| # | 文件 | 问题 | 修复 |
|---|------|------|------|
| 4 | data/fetcher.py | self.timeout 存了但没用，网络挂死冻结 app | 线程级 timeout 包装 |
| 5 | data/fetcher.py | 损坏的 parquet 缓存导致未捕获异常崩溃 | catch -> 删除损坏文件 -> 返回 None |
| 6 | data/fetcher.py | 空数据被当瞬态错误重试（浪费 2-4s/股） | EmptyDataError 不重试 |
| 7 | main.py | env var 占位符未展开 | 加载后递归 re.sub 展开 |
| 8 | main.py | config log_level 被忽略，硬编码 INFO | 读取配置应用 |

### Medium (健壮性)
| # | 文件 | 问题 | 修复 |
|---|------|------|------|
| 9 | risk/blacklist.py | except pass 吞掉黑名单损坏 | 改为 log.warning |
| 10 | weight_adjust.py | 熊市重分配用 w.get() 默认值重新添加被移除维度 | 只修改已有 key |
| 11 | main.py/workers/screening_tab | _stats 注入 results[0] 脆弱 | 改为 (results, stats) 元组 |
| 12 | main.py | print_summary 用显示数而非达标数 | 用 filtered_count |
| 13 | main.py | 行情数据缺失时 technical=50.0 | 改为 NaN |
| 14 | backtest/engine.py | 未兼容元组返回 | 加 isinstance 判断 |

## 测试
- 14/14 单元测试通过
- 8 个文件修改，+118/-41 行
