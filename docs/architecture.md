# 架构与算法说明

## 数据流

```text
生成目录 / 数据集文件夹 / 分别选择文件
                  |
                  v
          DatasetDescriptor
                  |
                  v
严格 FASTA/FASTQ/真值解析 -> GenomeBuffer(bytearray) + 50 ReadRecord
                  |
                  v
步长 1 滑窗 -> ChainedHashTable -> KmerEntry 冲突链
                                    |
                                    v
                              PositionNode 位置链
                  |
                  v
Read 前 K 位精确种子 -> 候选位置链 -> Hamming 比较/提前剪枝
                  |
                  v
BatchResult -> pywebview Bridge / CLI -> 四页同步展示 / JSON+CSV
```

## 必须手写的结构

`GenomeBuffer` 用固定长度 `bytearray` 保存大写 ASCII 碱基，一个碱基一个字节。哈希表的 `_buckets` 只是按下标保存桶头的数组，不提供键值映射能力。

`KmerEntry.next` 连接落入同一桶的不同 K-mer，解决哈希冲突。每个条目的 `positions_head`/`positions_tail` 指向另一种链表，`PositionNode.next` 连接同一 K-mer 的全部参考起点。位置采用尾插，天然保持严格升序并做到 O(1) 追加。

哈希函数把 `A/C/G/T` 分别编码为 `0/1/2/3`，逐位计算 base-4 整数并对质数桶容量取模。没有调用 Python `hash()`。

## 不变量

- 位置节点总数必须等于 `N-K+1`。
- 同一个 K-mer 在桶链中只能出现一次，其重复位置进入同一位置链。
- 每条位置链严格升序，尾指针的 `next` 必须为 `None`。
- 每个 K-mer 所在桶必须等于手写哈希函数的计算结果。
- 唯一键、非空桶、碰撞、最长桶链等统计必须与完整遍历一致。

## 检索

每条 Read 取前 K 个字符进行精确种子查找。候选位置不能越过参考序列尾部；合法候选从第 0 位逐字符比较。累计错配超过阈值时记录一次剪枝，并最多继续比较到 3 个错配，以便为失败 Read 保存近似对齐；超过 3 个错配后停止当前候选。完整比较且错配数不超过阈值时保存命中及每个错配的 Read 偏移、参考坐标和碱基变化。

生成器保护 Read 前 12 bp 不发生突变，因此生成数据在 K=4–12、阈值 3 时均能找回真实来源。外部数据不保证种子精确，这是课程指定算法的明确限制。检索结果还保留阈值内的最佳被拒绝候选（`nearest_hit`），供界面标红展示失败 Read 的真实近似位置。

## 复杂度

建索引时间约为 `O((N-K+1) * K)`，空间约为 `O(N + (N-K+1))`。批量检索时间约为 `O(R * (K + C * L))`，其中 `R` 是 Read 数、`C` 是平均候选数、`L` 是 Read 长度。提前剪枝不会改变最坏复杂度，但会减少实际比较字符数。

## 前后端状态

`DatasetService`、`SearchService` 和 `TaskController` 各自持有线程安全状态。`DesktopApi` 只做参数转换、原生对话框和后台任务调度。`start_*` 立即返回任务 ID；任务通过 `evaluate_js` 推送，同时前端每 500 ms 调用 `get_state()` 兜底。

四个页面不保存业务结果。`bridge-client.js` 恢复 Python 状态，`state-store.js` 在当前页面分发，页面脚本只保留筛选、分页、缩放和当前 Read 等视图状态。
