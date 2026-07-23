# Data

The training data is split into two parts (`benchmax_sft_iter1_part_aa.jsonl` and `benchmax_sft_iter1_part_ab.jsonl`) solely due to GitHub's 100 MB file size limit.

Before training, simply merge them into a single file:

```bash
cat benchmax_sft_iter1_part_aa.jsonl benchmax_sft_iter1_part_ab.jsonl > benchmax_sft_iter1.jsonl
```
