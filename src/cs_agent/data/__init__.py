"""数据管道：ingest → clean → split。

约束：clean 幂等；split 可复现；private 数据永不入库。
"""
