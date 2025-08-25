from app.app import create_app
from app.core.environment import load_app_env
from app.core.logging import setup_logging

# Set up logging configuration
setup_logging()

# #TODO: Improve load_dotenv to cater for docker instance vs uvicorn instance
load_app_env()

app = create_app()
