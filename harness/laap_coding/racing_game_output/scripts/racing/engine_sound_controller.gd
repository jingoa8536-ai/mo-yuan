class_name EngineSoundController
extends Node3D

@export var rpm_min: float = 1000.0
@export var rpm_max: float = 9000.0
@export var use_synth_fallback: bool = false
@export var volume_multiplier: float = 1.0

func update_engine(rpm: float, throttle: float, speed: float) -> void:
	# 更新引擎声音状态
	pass

func play_rev_sound() -> void:
	pass

func play_gear_shift(new_gear: int) -> void:
	pass

func _ready() -> void:
	pass

func _process(delta: float) -> void:
	pass