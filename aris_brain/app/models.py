from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime

class GeneratedClass(BaseModel):
    """设计数据模型和接口"""
    id: int
    name: str
    
    class Config:
        from_attributes = True

class GeneratedClassCreate(BaseModel):
    """设计数据模型和接口创建模型"""
    id: int
    name: str

class GeneratedClassUpdate(BaseModel):
    """设计数据模型和接口更新模型"""
    id: int
    name: str
