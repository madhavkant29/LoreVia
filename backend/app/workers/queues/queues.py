from kombu import Queue

TASK_QUEUES = [
    Queue("extraction",   routing_key="extraction"),
    Queue("analysis",     routing_key="analysis"),
    Queue("embedding",    routing_key="embedding"),
    Queue("intelligence", routing_key="intelligence"),
]
