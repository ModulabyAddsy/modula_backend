#terminal.py
from fastapi import APIRouter
from app.controller import terminal_controller

router = APIRouter()
router.include_router(terminal_controller.router)