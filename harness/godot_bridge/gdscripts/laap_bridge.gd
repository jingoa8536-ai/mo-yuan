#########################################################################
#  LAAP Bridge — JSON-RPC 2.0 server over TCP (port 6005)               #
#                                                                       #
#  This autoload exposes a running Godot instance to external clients   #
#  (the LAAP Python harness, test scripts, debugging tools) via the     #
#  JSON-RPC 2.0 protocol. Clients can introspect and drive the engine   #
#  by calling methods on Engine / EditorInterface / SceneTree /         #
#  ResourceLoader, or via the custom bridge methods listed below.       #
#                                                                       #
#  Transport:  TCP, port 6005 (configurable via `port` export var).     #
#  Framing:    Newline-delimited JSON — one JSON-RPC object per line.   #
#  Protocol:   JSON-RPC 2.0 —                                           #
#    Request:  {"jsonrpc":"2.0","method":"...","params":...,"id":N}\n   #
#    Response: {"jsonrpc":"2.0","result":...,"id":N}\n                  #
#               or {"jsonrpc":"2.0","error":{"code":C,"message":M},"id":N}\n #
#    Notification (no `id`): server processes but sends no reply.       #
#                                                                       #
#  Threading model:                                                     #
#    • Main thread  — `_process()` accepts new connections (TCPServer   #
#      is not thread-safe for accept) and runs the heartbeat sweep.     #
#    • Per-connection Thread — reads from StreamPeerTCP, dispatches     #
#      each JSON-RPC line through a shared JSONRPC instance, and        #
#      writes the response back. The JSONRPC methods map is populated   #
#      once at startup and treated as read-only thereafter, so          #
#      concurrent dispatch is safe; Callable invocations that touch      #
#      the SceneTree do so from the calling thread (callers must be     #
#      aware of Godot's main-thread affinity rules for scene edits).    #
#                                                                       #
#  Heartbeat: clients should send {"method":"ping"} at least every     #
#  25s; the server disconnects any peer silent for > 30s.              #
#                                                                       #
#  Usage: add this script as an Autoload singleton named "LAAPBridge"   #
#  (Project Settings → AutoLoad).                                       #
#########################################################################
extends Node
class_name LAAPBridge

# -- Configuration ------------------------------------------------------

## TCP port the JSON-RPC server listens on.
@export var port: int = 6005

## Seconds of silence before a client is forcefully disconnected.
@export var heartbeat_timeout: float = 30.0

# -- Internals ----------------------------------------------------------

var _server: TCPServer = null
var _jsonrpc: JSONRPC = null
var _connections: Array = []          # Array[Dictionary] — see _on_new_connection
var _connections_mutex: Mutex = null  # Guards _connections array mutations.
var _running: bool = false

# -- Lifecycle ----------------------------------------------------------

func _ready() -> void:
	_start_server()

func _exit_tree() -> void:
	_stop_server()

func _process(_delta: float) -> void:
	if not _running:
		return
	# Accept pending connections on the main thread — TCPServer.take_connection()
	# is not thread-safe, so we drain the accept queue here once per frame.
	while _server.is_connection_available():
		var peer: StreamPeerTCP = _server.take_connection()
		_on_new_connection(peer)
	# Drop clients that have exceeded the heartbeat timeout.
	_sweep_heartbeats()

# -- Server start / stop ------------------------------------------------

func _start_server() -> void:
	if _running:
		return
	_server = TCPServer.new()
	var err: int = _server.listen(port)
	if err != OK:
		push_error("LAAPBridge: failed to listen on port %d (error %d)" % [port, err])
		_server = null
		return
	_connections_mutex = Mutex.new()
	_jsonrpc = JSONRPC.new()
	_register_methods()
	_running = true
	print("LAAPBridge: JSON-RPC 2.0 server listening on port %d" % port)

func _stop_server() -> void:
	if not _running:
		return
	_running = false
	# Snapshot the connection list, then close each one (joins its thread).
	_connections_mutex.lock()
	var conns: Array = _connections.duplicate()
	_connections_mutex.unlock()
	for c in conns:
		_close_connection(c)
	_connections_mutex.lock()
	_connections.clear()
	_connections_mutex.unlock()
	if _server:
		_server.stop()
		_server = null
	print("LAAPBridge: server stopped")

# -- JSONRPC method registration ----------------------------------------

# Registers Godot core singletons and the custom LAAP bridge methods with
# the JSONRPC dispatcher. Each object's public methods are exposed under a
# "Scope.method_name" namespace, so a client can call e.g.:
#   {"method":"Engine.get_version_info","id":1}
# Custom bridge methods (ping, get_scene_tree, add_child, ...) are
# registered without a scope prefix for ergonomic short names.
#
# The JSONRPC class (Godot built-in, see modules/jsonrpc/jsonrpc.{h,cpp})
# keeps a HashMap<String, Callable> of method-name → callable. We populate
# it once here at startup; afterwards the map is treated as read-only by
# the per-connection threads, so concurrent process_string() calls are
# safe without additional locking on the dispatcher itself.
func _register_methods() -> void:
	_register_object_methods(Engine, "Engine")
	_register_object_methods(ResourceLoader, "ResourceLoader")
	_register_object_methods(get_tree(), "SceneTree")
	# EditorInterface is registered as an engine singleton only in editor
	# builds (editor/register_editor_types.cpp marks it editor_only=true),
	# so this branch is skipped at runtime in exported templates.
	if Engine.has_singleton("EditorInterface"):
		var ei: Object = Engine.get_singleton("EditorInterface")
		_register_object_methods(ei, "EditorInterface")

	# Custom LAAP bridge methods — short names, no scope prefix.
	_jsonrpc.set_method("ping", Callable(self, "_rpc_ping"))
	_jsonrpc.set_method("get_scene_tree", Callable(self, "_rpc_get_scene_tree"))
	_jsonrpc.set_method("add_child", Callable(self, "_rpc_add_child"))
	_jsonrpc.set_method("remove_node", Callable(self, "_rpc_remove_node"))
	_jsonrpc.set_method("set_property", Callable(self, "_rpc_set_property"))
	_jsonrpc.set_method("get_property", Callable(self, "_rpc_get_property"))
	_jsonrpc.set_method("call_method_on_node", Callable(self, "_rpc_call_method_on_node"))

# Enumerate the object's public methods and register each one under
# "<scope>.<method_name>". Private methods (leading underscore) are skipped
# to avoid exposing internal hooks by accident.
func _register_object_methods(obj: Object, scope: String) -> void:
	if obj == null:
		return
	for m in obj.get_method_list():
		var method_name: String = m["name"]
		if method_name.begins_with("_"):
			continue
		var rpc_name: String = "%s.%s" % [scope, method_name]
		_jsonrpc.set_method(rpc_name, Callable(obj, method_name))

# -- Connection handling ------------------------------------------------

# Per-connection state dictionary layout:
#   {
#     "peer":          StreamPeerTCP,  # the TCP socket
#     "thread":        Thread,         # handler thread
#     "last_activity": float,          # Time.get_ticks_msec() of last received byte
#     "alive":         bool,           # cleared to signal the thread to exit
#     "buffer":        String,         # accumulates partial lines until newline
#   }

func _on_new_connection(peer: StreamPeerTCP) -> void:
	peer.set_no_delay(true)  # disable Nagle for low-latency RPC
	var c: Dictionary = {
		"peer": peer,
		"thread": null,
		"last_activity": Time.get_ticks_msec(),
		"alive": true,
		"buffer": "",
	}
	var t: Thread = Thread.new()
	c["thread"] = t
	_connections_mutex.lock()
	_connections.append(c)
	_connections_mutex.unlock()
	# Thread.start invokes _connection_thread_func(c) on a worker thread.
	t.start(_connection_thread_func.bind(c))
	print("LAAPBridge: client connected (%d total)" % _connections.size())

# Connection thread entry point. Reads newline-delimited JSON-RPC messages,
# dispatches each through the shared JSONRPC instance, and writes the
# response back on the same socket.
func _connection_thread_func(c: Dictionary) -> void:
	var peer: StreamPeerTCP = c["peer"]
	while _running and c["alive"]:
		var status: int = peer.get_status()
		if status == StreamPeerTCP.STATUS_NONE or status == StreamPeerTCP.STATUS_ERROR:
			break
		peer.poll()  # update socket status / drain kernel buffers
		var available: int = peer.get_available_bytes()
		if available > 0:
			# Non-blocking read: available bytes are already buffered.
			var chunk: PackedByteArray = peer.get_data(available)[1]
			c["buffer"] += chunk.get_string_from_utf8()
			c["last_activity"] = Time.get_ticks_msec()
			# Dispatch every complete (newline-terminated) line in the buffer.
			while true:
				var nl: int = c["buffer"].find("\n")
				if nl == -1:
					break
				var line: String = c["buffer"].substr(0, nl)
				c["buffer"] = c["buffer"].substr(nl + 1)
				line = line.strip_edges()
				if line == "":
					continue
				# JSONRPC.process_string parses, dispatches, and returns the
				# JSON response string. Empty string means it was a
				# notification (no `id`) — no reply should be sent.
				var response: String = _jsonrpc.process_string(line)
				if response != "":
					peer.put_data((response + "\n").to_utf8_buffer())
		else:
			# No data pending — yield the CPU briefly to avoid a busy loop.
			OS.delay_msec(10)
	# Thread is exiting — disconnect the socket. We must NOT call
	# Thread.wait_to_finish() on ourselves; the main thread (or shutdown
	# path) is responsible for joining if needed.
	if peer.get_status() != StreamPeerTCP.STATUS_NONE:
		peer.disconnect_from_host()
	c["alive"] = false

# Close a connection from the main thread. Signals the handler thread to
# exit, disconnects the socket, and joins the thread.
func _close_connection(c: Dictionary) -> void:
	c["alive"] = false
	var peer: StreamPeerTCP = c["peer"]
	if peer and peer.get_status() != StreamPeerTCP.STATUS_NONE:
		peer.disconnect_from_host()
	var t: Thread = c["thread"]
	if t and t.is_started():
		t.wait_to_finish()
	_connections_mutex.lock()
	_connections.erase(c)
	_connections_mutex.unlock()

# Heartbeat sweep — disconnect any peer that has been silent for longer
# than `heartbeat_timeout` seconds. Runs on the main thread in _process.
func _sweep_heartbeats() -> void:
	var now: float = float(Time.get_ticks_msec())
	var timed_out: Array = []
	_connections_mutex.lock()
	for c in _connections:
		var elapsed: float = (now - float(c["last_activity"])) / 1000.0
		if elapsed > heartbeat_timeout:
			timed_out.append(c)
	_connections_mutex.unlock()
	for c in timed_out:
		print("LAAPBridge: heartbeat timeout — disconnecting client")
		_close_connection(c)

# -- Custom RPC methods -------------------------------------------------

## Returns "pong". Used as the heartbeat ping target.
func _rpc_ping() -> String:
	return "pong"

## Returns a recursive Dictionary describing the scene tree:
## {path, class, name, children: [...]}.
func _rpc_get_scene_tree() -> Dictionary:
	return _serialize_node(get_tree().root)

func _serialize_node(node: Node) -> Dictionary:
	var d: Dictionary = {
		"path": str(node.get_path()),
		"class": node.get_class(),
		"name": String(node.name),
		"children": [],
	}
	for child in node.get_children():
		d["children"].append(_serialize_node(child))
	return d

## Instantiates a new node of `child_type` (ClassDB name), names it
## `child_name`, adds it as a child of the node at `parent_path`, and
## returns the new node's path. Returns "" on failure.
func _rpc_add_child(parent_path: String, child_type: String, child_name: String) -> String:
	var parent: Node = get_node_or_null(parent_path)
	if parent == null:
		push_error("LAAPBridge: add_child — parent not found: %s" % parent_path)
		return ""
	if not ClassDB.class_exists(child_type):
		push_error("LAAPBridge: add_child — unknown class: %s" % child_type)
		return ""
	var child: Node = ClassDB.instantiate(child_type)
	if child == null:
		push_error("LAAPBridge: add_child — failed to instantiate: %s" % child_type)
		return ""
	child.name = child_name
	parent.add_child(child)
	return str(child.get_path())

## Removes (and queue_frees) the node at `path`.
func _rpc_remove_node(path: String) -> void:
	var node: Node = get_node_or_null(path)
	if node == null:
		push_error("LAAPBridge: remove_node — node not found: %s" % path)
		return
	var parent: Node = node.get_parent()
	if parent:
		parent.remove_child(node)
	node.queue_free()

## Sets property `prop` on the node at `path` to `value`.
func _rpc_set_property(path: String, prop: String, value: Variant) -> void:
	var node: Node = get_node_or_null(path)
	if node == null:
		push_error("LAAPBridge: set_property — node not found: %s" % path)
		return
	node.set(prop, value)

## Returns the value of property `prop` on the node at `path`.
func _rpc_get_property(path: String, prop: String) -> Variant:
	var node: Node = get_node_or_null(path)
	if node == null:
		push_error("LAAPBridge: get_property — node not found: %s" % path)
		return null
	return node.get(prop)

## Calls `method` on the node at `path` with `args` (Array) and returns
## the result.
func _rpc_call_method_on_node(path: String, method: String, args: Array) -> Variant:
	var node: Node = get_node_or_null(path)
	if node == null:
		push_error("LAAPBridge: call_method_on_node — node not found: %s" % path)
		return null
	return node.callv(method, args)
