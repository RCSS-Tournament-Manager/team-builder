import aio_pika

class RabbitMQ:
    def __init__(self, loop, server, consuming_queue , publishing_queue):
        self.loop = loop
        self.server = server
        self.queue = consuming_queue
        self.route = publishing_queue
        self.connection = None
        self.channel = None
        self.queue_instance = None
        self.response_list = list()

    async def connect(self):
        self.connection = await aio_pika.connect_robust(self.server, loop=self.loop)
        self.channel = await self.connection.channel()
        self.queue_instance = await self.channel.declare_queue(self.queue)

    async def close(self):
        if self.channel:
            await self.channel.close()
        if self.connection:
            await self.connection.close()
    
    async def add_message_handler(self, handler):
        self.loop.create_task(self.queue_instance.consume(handler))

    async def publish(self,msg:str):
        self.channel.basic_publish(exchange='',
                      routing_key=self.route,
                      body=msg)
    
    async def consume(self):
        self.channel.basic_consume(queue=self.queue,
                        on_message_callback=self.callback,
                        auto_ack=True)
    async def is_connect(self):
        return self.connection.is_open

        
        