class_name EngineSoundController
extends Node3D

@export var rpm_min: float = 1000.0
@export var rpm_max: float = 9000.0
@export var use_synth_fallback: bool = false
@export var volume_multiplier: float = 1.0

var current_rpm: float = 1000.0
var audio_player: AudioStreamPlayer3D = null

func _ready():
	audio_player = get_node_or_null("EngineSound3D")
	if audio_player:
		print("EngineSoundController: Found audio player")
	else:
		print("EngineSoundController: Audio player not found")
	
	print("EngineSoundController: Ready (waiting for parent vehicle)")

func update_engine(rpm: float, throttle: float, speed: float) -> void:
	current_rpm = rpm
	
	var rpm_ratio = clamp((rpm - rpm_min) / (rpm_max - rpm_min), 0.0, 1.0)
	
	if audio_player:
		audio_player.volume_db = -20.0 + (rpm_ratio * 10.0)
	
	print("Engine RPM: %d, Throttle: %.2f, Speed: %.2f" % [rpm, throttle, speed])

func play_rev_sound() -> void:
	if audio_player:
		audio_player.play()

func play_gear_shift(new_gear: int) -> void:
	print("Gear shift to: %d" % new_gear)

func _process(delta: float) -> void:
	var vehicle = get_parent()
	if vehicle is VehicleBody3D:
		var speed = vehicle.linear_velocity.length()
		var rpm = rpm_min + (speed / 30.0) * (rpm_max - rpm_min)
		update_engine(rpm, 0.5, speed)
