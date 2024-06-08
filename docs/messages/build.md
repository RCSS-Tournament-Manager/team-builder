
```json
message format :
{
    "command": "build",
    "body": {
        "build_id": "1234",
        "image_name": "teamA",
        "image_tag": "latest",

        "file":{
            "type": "minio",
            "config": {
                "endpoint": "http://minio:9000",
                "access_key": "access_key",
                "secret_key": "secret_key",
            },
            "bucket": "bucket",
            "file_id": "1234"
        },
        "registry":{
            "config": {
                "host": "",
                "port": 1234,
                "username": "username",
                "password": "password",
            }  

        },
        "log": {
            "level": "info",
            "stream": {
                "build": {
                    "type": "rabbitmq",
                    "host": "rabbitmq",
                    "port": 5672,
                    "username": "username",
                    "password": "password",
                    "exchange": "exchange",
                    "queue": "queue",                    
                },
            }
        }
        
        
        
    }
}
```