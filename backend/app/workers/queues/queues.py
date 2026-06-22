from kombu import Queue

TASK_QUEUES = [
    Queue("extraction", routing_key="extraction"),
    Queue("extraction_priority", routing_key="extraction_priority"),
    Queue("analysis", routing_key="analysis"),
    Queue("analysis_priority", routing_key="analysis_priority"),
    Queue("embedding", routing_key="embedding"),
    Queue("intelligence", routing_key="intelligence"),
]
