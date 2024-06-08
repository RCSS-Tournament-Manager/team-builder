
```json
message format :
{
    "command": "build",
    "body": {
        "build_id": "1234",
        "team_name": "teamA",
        "image_name": "teamA",
        "image_tag": "latest",


        "team_dockerfile": {
            "_type": "minio",
            "_config": {
                "endpoint": "http://minio:9000",
                "access_key": "access_key",
                "secret_key": "secret_key",
            },
            "bucket": "bucket",
            "file_id": "1234"
        }, 

        "file":{
            "_type": "minio",
            "_config": {
                "endpoint": "http://minio:9000",
                "access_key": "access_key",
                "secret_key": "secret_key",
            },
            "bucket": "bucket",
            "file_id": "1234"
        },

        "registry":{
            "_type": "docker",
            "_config": {
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
                    "_type": "rabbitmq",
                    "_config": {
                        "host": "rabbitmq",
                        "port": 5672,
                        "username": "username",
                        "password": "password",
                                            
                    },
                    "queue": "queue",                    
                },
            }
        }
        
    }
}
```