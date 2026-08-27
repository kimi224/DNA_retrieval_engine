# 数据格式

## 数据集目录

```text
dna_demo_YYYYMMDD_HHMMSS_seed_N/
├── reference.fasta
├── reads.fastq
└── ground_truth.json
```

生成器始终新建唯一子目录，不覆盖既有数据。文件先写入同目录临时文件，完成后用 `os.replace` 原子替换。

## FASTA

- 只接受 `.fa` 或 `.fasta`。
- 恰好一条参考序列，长度 2,000–5,000 bp。
- 标题首词为参考序列 ID。
- 序列忽略空行后拼接，只允许大写或可转换为大写的 `A/C/G/T`。
- 生成文件每行 80 个碱基。

## FASTQ

- 只接受 `.fq` 或 `.fastq`。
- 恰好 50 条四行记录，每条 50–150 bp。
- Read ID 不得重复，序列只允许 `A/C/G/T`。
- 质量字符串必须与序列等长；生成数据使用 `I` 作为 Q40 占位。本项目的 Hamming 检索不使用质量分数。

## ground_truth.json

真值文件可选，只用于可复现记录、自动测试和“是否找回真实来源”展示，不参与候选搜索。主要字段包括：

- `schema_version`: 当前为 1。
- `dataset_id`、`created_at`、`random_seed`。
- `coordinate_system`: 内部为 0-based 半开区间，界面为 1-based 闭区间。
- `generator`: 参考长度、Read 数、长度范围、错配范围和种子保护长度。
- `checksums`: FASTA 与 FASTQ 的 SHA-256。
- `reads`: 每条 Read 的真实起点、错配偏移和碱基变化。

## 文件夹发现

只检查所选文件夹当前层，不递归。优先使用规范文件名 `reference.fasta` 和 `reads.fastq`；若不存在，分别寻找唯一的 FASTA/FASTQ 候选。缺失或同类候选超过一个均明确报错。`ground_truth.json` 缺失不影响普通检索。
