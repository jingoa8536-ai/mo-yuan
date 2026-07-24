class_name GhostRecorder
extends Node3D

@export var record_interval: float = 0.05
@export var max_record_time: float = 600.0
@export var is_recording: bool = false

func start_recording() -> void:
	pass

func stop_recording() -> void:
	pass

func save_recording(filename: String) -> void:
	pass

func load_recording(filename: String) -> void:
	pass

func finish_lap() -> void:
	pass