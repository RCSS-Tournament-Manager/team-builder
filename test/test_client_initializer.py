from src.utils.client_initializer import initialize_clients

import pprint



async def run():
    data = {
        "minio": {
            "_type": "minio", # must return default
        },
        "docker": {
            "_type": "docker",
            "_config": {
                'default_registry':"localhost:5000",
                'username':"",
                'password':""
            }
            # must return new docker object
        },
        "docker_invalid": {
            "_type": "docker",
            "_config": {
                'default_registry':"localhost:5000",
                'ee':"",
            }
            # must return default docker object
        },
        "rabbitmq": {
            "_type": "rabbitmq",
            "_config": 'default' # must return default
        }
    }
    print("Before:")
    pprint.pprint(data)
    data,errors = initialize_clients(
        data,
        minio="minio",
        docker="docker",
        rabbitmq="rabbitmq"
    )
    print("After:")
    pprint.pprint(data)
    
    print("Errors:")
    pprint.pprint(errors)
    
    
    
    