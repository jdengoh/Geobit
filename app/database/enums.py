"""
Database enumerations for the application.
"""

from enum import Enum


class UserType(Enum):
    """User types enum"""

    ADMIN = "admin"
    USER = "user"


    
