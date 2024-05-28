from typing import Union

from pydantic import BaseModel



class ImageBuildedResponse(BaseModel):
    name: str
    tag: str