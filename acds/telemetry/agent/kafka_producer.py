import json
import logging
from confluent_kafka import Producer
from config import KAFKA_CONFIG, KAFKA_TOPIC

logger = logging.getLogger(__name__)

class TelemetryProducer:
    def __init__(self):
        self.producer = Producer(KAFKA_CONFIG)
        self.topic = KAFKA_TOPIC

    def delivery_report(self, err, msg):
        """ 
        Called once for each message produced to indicate delivery result.
        Triggered by poll() or flush().
        """
        if err is not None:
            logger.error(f"Message delivery failed: {err}")
        else:
            # Uncomment for noisy debugging of delivery status
            # logger.debug(f"Message delivered to {msg.topic()} [{msg.partition()}]")
            pass

    def produce(self, telemetry_dict):
        """ 
        Publish a telemetry dictionary back to Kafka as serialized JSON.
        """
        try:
            val = json.dumps(telemetry_dict)
            self.producer.produce(
                self.topic, 
                value=val.encode('utf-8'),
                callback=self.delivery_report
            )
            
            # Since KAFKA_CONFIG has 'linger.ms'=1, we can poll lightly to immediately 
            # serve delivery callbacks and stream data without batch delays.
            self.producer.poll(0)
            
        except BufferError:
            logger.warning("Local Kafka producer queue is full. Flushing...")
            self.producer.poll(0.1)
            # Re-try produce
            self.produce(telemetry_dict)
        except Exception as e:
            logger.error(f"Failed to produce message: {e}")

    def flush(self):
        """ 
        Ensure all messages are delivered before script exit. 
        """
        logger.info("Flushing Kafka producer...")
        self.producer.flush()
