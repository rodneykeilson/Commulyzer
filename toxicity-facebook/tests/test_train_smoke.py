import pytest  # type: ignore

torch = pytest.importorskip("torch")  # type: ignore

from train import train_toxicity


class DummyTokenizer:
    def __init__(self):
        pass

    def __call__(self, texts, padding=True, truncation=True, return_tensors=None):
        max_len = max(len(t) for t in texts) if texts else 0
        arr = torch.ones((len(texts), max_len), dtype=torch.long)
        return {"input_ids": arr, "attention_mask": arr}

    @staticmethod
    def from_pretrained(path):  # type: ignore
        return DummyTokenizer()

    def save_pretrained(self, path):  # pragma: no cover
        pass


def test_predict_texts_returns_scores(monkeypatch):
    class DummyModel(torch.nn.Module):
        @staticmethod
        def from_pretrained(path, num_labels=2):  # type: ignore
            model = DummyModel()
            model.num_labels = num_labels
            return model

        def forward(self, input_ids=None, attention_mask=None):  # type: ignore
            batch_size = input_ids.shape[0]
            logits = torch.zeros((batch_size, 2))
            logits[:, 1] = 0.7
            return type("Output", (), {"logits": logits})

    monkeypatch.setattr(train_toxicity, "AutoTokenizer", DummyTokenizer, raising=False)
    monkeypatch.setattr(train_toxicity, "AutoModelForSequenceClassification", DummyModel, raising=False)

    texts = ["halo", "dunia"]
    result = train_toxicity.predict_texts("dummy", texts)
    assert len(result["scores"]) == len(texts)
    assert all(0 <= score <= 1 for score in result["scores"])
