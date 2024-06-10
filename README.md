# Team Builder

Team builder service is a service that download a team binary from a s3 bucket and build a docker image of team binary and push it to a docker registry.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Python 3.10](https://www.python.org/downloads/)
- [Pipenv](https://pypi.org/project/pipenv/)


## Run for development

1. Install dependencies
```bash
pipenv install
```

2.Create an env variable file like env.example

3. Run the service
```bash
docker-compose up -d 
```

4. Run the service
```bash
pipenv run python builder-service.py
```

## Information 

### [RoboCup](https://www.robocup.org/)
RoboCup is an international robotics competition that focuses on promoting research and development in the field of autonomous robots. The competition aims to advance the state of the art in robotics and artificial intelligence by challenging teams to develop robots capable of playing soccer, rescue, and other tasks against other teams in a real-world or simulated environments.
### [Soccer Simulation 2D](https://ssim.robocup.org/)
The RoboCup Soccer Simulation 2D (SS2D) is one of the leagues within the RoboCup competition. It involves simulating a soccer game using virtual robots controlled by autonomous software agents. The objective is to develop intelligent strategies and algorithms that enable the virtual robots to play soccer effectively.

### [RoboCup Soccer Simulation Tournament Manager](https://github.com/RCSS-Tournament-Manager)
RCSS-Tournament-Manager (RoboCup Soccer Simulation Tournament Manager) is a project that aims to provide a simple and easy to use tournament manager for the RoboCup Soccer Simulation 2D.

If you want to know more about how this project works, you can read the [project documentation](https://github.com/RCSS-Tournament-Manager/docs).

### [Team Builder](https://github.com/RCSS-Tournament-Manager/team-builder)
This project is an integral component of the [RCSS-Tournament-Manager](https://github.com/RCSS-Tournament-Manager) project. Its primary objective is to build teams and prepare them for the [Runner service](https://github.com/RCSS-Tournament-Manager/runner), which run games between two teams.

The service operates by retrieving [messages](docs/messages.md) from the message broker service. Upon receiving a message, it proceeds to fetch team files from the storage service. Subsequently, it processes and refines these files to construct complete team profiles. Finally, the service seamlessly uploads these refined profiles to a Docker registry for further utilization.

## License
This project is licensed under the AGPL-3.0 License - see the [LICENSE](LICENSE) file for details.

