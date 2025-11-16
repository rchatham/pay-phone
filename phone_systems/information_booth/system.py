#!/usr/bin/env python3
"""
Information Booth Phone System

A simple information phone system with weather, time, jokes, and music options.
"""
from payphone.core import PhoneSystemBase, PhoneTree


class InformationBoothSystem(PhoneSystemBase):
    """
    Information booth phone system with multiple menu options.

    Menu structure:
    - Main Menu
      - 1: Information Menu
        - 1: Weather Info
        - 2: Time Info
      - 2: Jokes
      - 3: Music
    """

    def setup_phone_tree(self) -> PhoneTree:
        """Build the phone menu tree for the information booth"""
        # Reuse the same audio handler for all nodes to avoid multiple pygame inits
        audio = self.audio_handler

        # Leaf nodes
        weather = PhoneTree("menu/weather_info.mp3", audio_handler=audio)
        time_info = PhoneTree("menu/time_info.mp3", audio_handler=audio)

        # Branch nodes
        info_menu = PhoneTree(
            "menu/info_menu.mp3",
            audio_handler=audio,
            options={
                "1": weather,
                "2": time_info
            }
        )

        # Root menu
        main_menu = PhoneTree(
            "menu/main_menu.mp3",
            audio_handler=audio,
            options={
                "1": info_menu,
                "2": PhoneTree("menu/jokes.mp3", audio_handler=audio),
                "3": PhoneTree("menu/music.mp3", audio_handler=audio)
            }
        )

        return main_menu
