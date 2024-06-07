import time
import pika
from src.rabbitmq import RabbitMQ

def main():
    rabbit = RabbitMQ()
    while True:
        #checking the message 

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)