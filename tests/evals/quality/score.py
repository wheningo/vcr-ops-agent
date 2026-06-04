"""分类指标统计 — 准确率 / 精确率 / 召回率 / 误报率"""

from dataclasses import dataclass


@dataclass
class ClsCounts:
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0

    def add(self, predicted: bool, expected: bool) -> None:
        if predicted and expected:
            self.tp += 1
        elif predicted and not expected:
            self.fp += 1
        elif not predicted and not expected:
            self.tn += 1
        else:
            self.fn += 1

    @property
    def accuracy(self) -> float:
        d = self.tp + self.fp + self.tn + self.fn
        return (self.tp + self.tn) / d if d else 0

    @property
    def precision(self) -> float:
        d = self.tp + self.fp
        return self.tp / d if d else 0

    @property
    def recall(self) -> float:
        d = self.tp + self.fn
        return self.tp / d if d else 0

    @property
    def fp_rate(self) -> float:
        """误报率 = FP / (FP + TN)"""
        d = self.fp + self.tn
        return self.fp / d if d else 0

    def summary(self) -> str:
        return (
            f"accuracy={self.accuracy:.2f} precision={self.precision:.2f} "
            f"recall={self.recall:.2f} 误报率={self.fp_rate:.2f} "
            f"(TP={self.tp} FP={self.fp} TN={self.tn} FN={self.fn})"
        )