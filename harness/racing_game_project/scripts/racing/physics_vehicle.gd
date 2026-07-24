class_name PhysicsVehicle
extends VehicleBody3D

@export var engine_power: float = 300.0
@export var max_steering: float = 0.5
@export var brake_power: float = 10.0
@export var max_speed: float = 50.0

var acceleration_input: float = 0.0
var steering_input: float = 0.0

func _ready():
	print("  [OK] PhysicsVehicle ready")

func _physics_process(delta):
	# In headless mode, just simulate forward motion
	if not Engine.has_singleton("Input"):
		engine_force = engine_power * 0.3
		steering = 0.0
		var current_speed = linear_velocity.length()
		if current_speed > max_speed:
			linear_velocity = linear_velocity.normalized() * max_speed
		return
	
	acceleration_input = Input.get_axis("backward", "forward")
	steering_input = Input.get_axis("right", "left")
	
	# Apply engine force
	if acceleration_input > 0:
		engine_force = acceleration_input * engine_power
		brake = 0.0
	elif acceleration_input < 0:
		engine_force = 0.0
		brake = brake_power
	else:
		engine_force = 0.0
		brake = 0.0
	
	# Apply steering (Godot 4 property)
	steering = steering_input * max_steering
	
	# Clamp speed (Godot 4: use linear_velocity)
	var current_speed = linear_velocity.length()
	if current_speed > max_speed:
		linear_velocity = linear_velocity.normalized() * max_speed

func start():
	engine_force = 0.0
	steering = 0.0
	linear_velocity = Vector3.ZERO
