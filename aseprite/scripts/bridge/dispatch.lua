local request_path = app.params["request"]
local response_path = app.params["response"]
if request_path == nil or response_path == nil then
  error("bridge requires request and response script parameters")
end

local ok, response = xpcall(function()
  local request = json.decode(read_all(request_path))
  if request.protocol_version ~= BRIDGE_PROTOCOL_VERSION then
    fail("BRIDGE_PROTOCOL_ERROR", "unsupported bridge protocol version")
  end
  local operation = operations[request.operation]
  if operation == nil then fail("BRIDGE_PROTOCOL_ERROR", "unknown bridge operation") end
  return { ok = true, result = operation(request.input or {}) }
end, function(message)
  return debug.traceback(tostring(message), 2)
end)

if not ok then
  response = { ok = false, error = { code = "ASEPRITE_FAILED", message = tostring(response) } }
  local code, message = string.match(response.error.message, "^([A-Z_]+): (.*)$")
  if code ~= nil then
    response.error.code = code
    response.error.message = message
  end
end

write_all(response_path, json.encode(response))
