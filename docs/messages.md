# Messages

All messages are sent in JSON format. The message format is as follows:

```json
{
  "command": "messageType",
  "body": {
    "key1": "value1",
    "key2": "value2"
  }
}
```


List of available messages:
1. [Build team](messages/build.md)
2. [Kill build](messages/KillBuild.md)
