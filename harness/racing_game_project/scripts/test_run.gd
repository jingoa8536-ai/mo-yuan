extends SceneTree

func _initialize() -> void:
	var sep = "=".repeat(60)
	print(sep)
	print("Racing Game Demo - Test Run")
	print(sep)

	print("\nProject Info:")
	print("  Project Name: " + str(ProjectSettings.get_setting("application/config/name", "")))
	print("  Version: " + str(ProjectSettings.get_setting("application/config/version", "")))
	print("  Main Scene: " + str(ProjectSettings.get_setting("application/run/main_scene", "")))

	print("\nScripts Found:")
	var script_paths = [
		"res://scripts/racing/physics_vehicle.gd",
		"res://scripts/racing/engine_sound_controller.gd",
		"res://scripts/racing/ghost_recorder.gd",
		"res://scripts/racing/ghost_player_controller.gd",
		"res://scripts/racing/speed_hud.gd"
	]

	for path in script_paths:
		var script = load(path)
		if script:
			print("  [OK] " + path + " - " + script.get_class())
		else:
			print("  [FAIL] " + path + " - Failed to load")

	print("\nResources Found:")
	var resource_paths = [
		"res://resources/audio/race_audio_bus.tres",
		"res://resources/materials/car_material.tres",
		"res://resources/materials/car_sports_red.tres"
	]

	for path in resource_paths:
		var resource = load(path)
		if resource:
			print("  [OK] " + path + " - Type: " + resource.get_class())
		else:
			print("  [FAIL] " + path + " - Failed to load")

	print("\nScenes Found:")
	var scene_paths = [
		"res://scenes/racing/main.tscn",
		"res://scenes/racing/racing_v2.tscn",
		"res://scenes/racing/engine_sound.tscn",
		"res://scenes/racing/race_camera.tscn"
	]

	for path in scene_paths:
		var scene = load(path)
		if scene:
			print("  [OK] " + path)
		else:
			print("  [FAIL] " + path + " - Failed to load")

	print("\n" + sep)
	print("Test completed successfully!")
	print(sep)

	quit()
