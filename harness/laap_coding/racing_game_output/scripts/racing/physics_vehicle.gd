class_name PhysicsVehicle
extends VehicleBody3D

@export var max_speed: float = 300.0
@export var acceleration: float = 20.0
@export var brake_force: float = 30.0
@export var steering_angle: float = 0.5

func apply_throttle(amount: float) -> void:
	pass

func apply_brake(amount: float) -> void:
	pass

func steer(angle: float) -> void:
	pass

func get_current_rpm() -> float:
	return null

func get_current_speed() -> float:
	return null

func _physics_process(delta: float) -> void:
	pass