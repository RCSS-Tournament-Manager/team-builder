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
1. Run the service
```bash
pipenv run python -m uvicorn builder-service:app --reload
```

# TODO

- [ ] change the messages 
- [ ] change dockerfile


## License
This project is licensed under the AGPL-3.0 License - see the [LICENSE](LICENSE) file for details.

