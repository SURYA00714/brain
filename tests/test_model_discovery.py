import unittest
from unittest.mock import patch, MagicMock
from models.gateway import ModelGateway, OllamaProvider

class TestModelDiscovery(unittest.TestCase):
    @patch("requests.get")
    def test_discover_local_models(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "models": [
                {"name": "qwen3.5:2b-q4_K_M", "size": 1900000000, "details": {"parameter_size": "2B", "quantization_level": "Q4_K_M"}},
                {"name": "qwen3.5-brain:v2", "size": 1300000000, "details": {"parameter_size": "2B", "quantization_level": "Q4_K_M"}}
            ]
        }
        mock_get.return_value = mock_resp

        gateway = ModelGateway()
        models = gateway.discover_local_models()
        self.assertEqual(len(models), 2)
        self.assertEqual(models[0]["name"], "qwen3.5:2b-q4_K_M")
        self.assertEqual(models[1]["name"], "qwen3.5-brain:v2")

    @patch("requests.get", side_effect=Exception("Connection refused"))
    def test_discover_local_models_offline(self, mock_get):
        gateway = ModelGateway()
        models = gateway.discover_local_models()
        self.assertEqual(models, [])

if __name__ == "__main__":
    unittest.main()
