import logging
from prometheus_client import start_http_server, Info, Counter

class PrometheusMetrics:

    def __init__(self, name: str, port: int):
        self._log = logging.getLogger('errbot.backends.hangoutschat')
        self._name = self.normalize_name(name)
        self._port = port
        self._metrics = {
            "message_sent": Counter(f"{self._name}_message_sent","The number of sent messages by result status", ['status']),
            # New metrics can be defined here
        }
        self._log.info(f"Found {len(self._metrics)} configured prometheus metrics")

    def normalize_name(self, name):
        return name.replace('@','').strip().lower()
    
    def metric(self, name):
        return self._metrics.get(name)
    
    def metrics(self):
        return self._metrics
    
    def start_server(self):
        start_http_server(self._port)
        self._log.info(f"Metrics available on port {self._port}")