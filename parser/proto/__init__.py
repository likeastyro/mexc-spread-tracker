"""Локальный sys.path-хак для protobuf-генерированных _pb2 файлов.
Внутри них импорты плоские (без префикса пакета), поэтому добавляем
эту папку в sys.path при первом импорте из пакета.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))