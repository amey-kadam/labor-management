import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'you-should-change-this')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'postgresql://postgres:123@localhost:5432/labor'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
