from __future__ import annotations
from functools import lru_cache
import pygame


@lru_cache(maxsize=None)
def get_font(size: int) -> pygame.font.Font:
    return pygame.font.SysFont(None, size)


@lru_cache(maxsize=512)
def render_text(text: str, size: int,
                color: tuple[int, int, int]) -> pygame.Surface:
    return get_font(size).render(text, True, color)
