class_name SpeedHUD
extends CanvasLayer

## Overlay HUD that shows the player's current speed in km/h.
## Lives as a CanvasLayer so it renders on top of the 3D viewport.

var _car: Node3D = null
var _label: Label = null

func _ready() -> void:
	_label = Label.new()
	_label.add_theme_font_size_override("font_size", 24)
	_label.position = Vector2(20, 20)
	add_child(_label)

	_car = _find_car()
	if _car:
		print("  [OK] SpeedHUD ready - tracking: " + _car.name)
	else:
		print("  [OK] SpeedHUD ready (no car found)")

func _process(_delta: float) -> void:
	if _car == null:
		_car = _find_car()

	if _car and _label:
		var speed: float = _car.linear_velocity.length() * 3.6  # m/s to km/h
		_label.text = "Speed: " + str(round(speed)) + " km/h"
	elif _label:
		_label.text = "Speed: --- km/h (no car)"

## Safely resolves the player vehicle from the current scene root.
func _find_car() -> Node3D:
	var root := get_tree().current_scene
	if root != null and root.has_node("Car"):
		return root.get_node("Car") as Node3D
	return null
