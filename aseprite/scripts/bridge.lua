-- Versioned, fixed-operation bridge between the Python server and Aseprite.

local BRIDGE_PROTOCOL_VERSION = 1

local function read_all(path)
  local file, open_error = io.open(path, "rb")
  if not file then error("cannot open request file: " .. tostring(open_error)) end
  local content = file:read("*a")
  file:close()
  return content
end

local function write_all(path, content)
  local file, open_error = io.open(path, "wb")
  if not file then error("cannot open response file: " .. tostring(open_error)) end
  file:write(content)
  file:close()
end

local function fail(code, message)
  error(code .. ": " .. message, 0)
end

local function color_mode_name(mode)
  if mode == ColorMode.RGB then return "rgb" end
  if mode == ColorMode.GRAY then return "grayscale" end
  if mode == ColorMode.INDEXED then return "indexed" end
  if mode == ColorMode.TILEMAP then return "tilemap" end
  return "unknown"
end

local function animation_direction_name(direction)
  if direction == AniDir.FORWARD then return "forward" end
  if direction == AniDir.REVERSE then return "reverse" end
  if direction == AniDir.PING_PONG then return "ping_pong" end
  if direction == AniDir.PING_PONG_REVERSE then return "ping_pong_reverse" end
  return tostring(direction)
end

local function rectangle_info(rectangle)
  if rectangle == nil then return nil end
  return {
    x = rectangle.x,
    y = rectangle.y,
    width = rectangle.width,
    height = rectangle.height
  }
end

local function point_info(point)
  if point == nil then return nil end
  return { x = point.x, y = point.y }
end

local function layer_type(layer)
  if layer.isGroup then return "group" end
  if layer.isTilemap then return "tilemap" end
  if layer.isBackground then return "background" end
  return "image"
end

local function inspect_layer(layer, parent_path)
  local path = layer.name
  if parent_path ~= "" then path = parent_path .. "/" .. layer.name end
  local children = {}
  if layer.isGroup then
    for _, child in ipairs(layer.layers) do
      table.insert(children, inspect_layer(child, path))
    end
  end
  return {
    name = layer.name,
    path = path,
    type = layer_type(layer),
    visible = layer.isVisible,
    editable = layer.isEditable,
    opacity = layer.opacity or 255,
    blend_mode = layer.blendMode and tostring(layer.blendMode) or "normal",
    cel_count = #layer.cels,
    children = children
  }
end

local function color_info(color)
  return {
    red = color.red,
    green = color.green,
    blue = color.blue,
    alpha = color.alpha,
    hex = string.format("#%02X%02X%02X%02X", color.red, color.green, color.blue, color.alpha)
  }
end

local function inspect_sprite(sprite, include_palette_colors, source_path)
  local frames = {}
  for _, frame in ipairs(sprite.frames) do
    table.insert(frames, {
      index = frame.frameNumber - 1,
      duration_ms = math.floor(frame.duration * 1000 + 0.5)
    })
  end

  local layers = {}
  for _, layer in ipairs(sprite.layers) do
    table.insert(layers, inspect_layer(layer, ""))
  end

  local tags = {}
  for _, tag in ipairs(sprite.tags) do
    table.insert(tags, {
      name = tag.name,
      from_frame = tag.fromFrame.frameNumber - 1,
      to_frame = tag.toFrame.frameNumber - 1,
      direction = animation_direction_name(tag.aniDir),
      repeats = tag.repeats or 0
    })
  end

  -- The Lua API exposes slice geometry for the active frame. Return that key;
  -- sprite-sheet JSON export remains the source for complete animated slice keys.
  local slices = {}
  for _, slice in ipairs(sprite.slices) do
    table.insert(slices, {
      name = slice.name,
      keys = {{
        frame = 0,
        bounds = rectangle_info(slice.bounds),
        center = rectangle_info(slice.center),
        pivot = point_info(slice.pivot)
      }}
    })
  end

  local palettes = {}
  for palette_index = 1, #sprite.palettes do
    local palette = sprite.palettes[palette_index]
    local colors = nil
    if include_palette_colors then
      colors = {}
      for index = 0, #palette - 1 do
        table.insert(colors, color_info(palette:getColor(index)))
      end
    end
    local palette_frame = 0
    if type(palette.frame) == "number" then
      palette_frame = palette.frame - 1
    elseif palette.frame ~= nil then
      palette_frame = palette.frame.frameNumber - 1
    end
    table.insert(palettes, { frame = palette_frame, size = #palette, colors = colors })
  end

  return {
    source_path = source_path,
    width = sprite.width,
    height = sprite.height,
    color_mode = color_mode_name(sprite.colorMode),
    transparent_color = sprite.transparentColor,
    pixel_ratio = { width = sprite.pixelRatio.width, height = sprite.pixelRatio.height },
    frame_count = #sprite.frames,
    frames = frames,
    layers = layers,
    tags = tags,
    slices = slices,
    palettes = palettes
  }
end

local function open_sprite(path)
  local sprite = app.open(path)
  if sprite == nil then fail("INVALID_SPRITE", "Aseprite could not open the source document") end
  return sprite
end

local function parse_color(value)
  if type(value) ~= "string" or (string.len(value) ~= 7 and string.len(value) ~= 9) then
    fail("INVALID_COLOR", "color must be #RRGGBB or #RRGGBBAA")
  end
  local red = tonumber(string.sub(value, 2, 3), 16)
  local green = tonumber(string.sub(value, 4, 5), 16)
  local blue = tonumber(string.sub(value, 6, 7), 16)
  local alpha = 255
  if string.len(value) == 9 then alpha = tonumber(string.sub(value, 8, 9), 16) end
  if red == nil or green == nil or blue == nil or alpha == nil then
    fail("INVALID_COLOR", "color contains invalid hexadecimal digits")
  end
  return Color { r = red, g = green, b = blue, a = alpha }
end

local function find_layer(sprite, path)
  local current = sprite.layers
  local found = nil
  for part in string.gmatch(path, "[^/]+") do
    found = nil
    for _, candidate in ipairs(current) do
      if candidate.name == part then
        if found ~= nil then fail("INVALID_SELECTOR", "layer path is ambiguous: " .. path) end
        found = candidate
      end
    end
    if found == nil then fail("INVALID_SELECTOR", "layer was not found: " .. path) end
    current = found.layers or {}
  end
  return found
end

local function draw_pixels(sprite, layer, frame_number, pixels)
  if layer.isGroup or layer.isTilemap then
    fail("INVALID_SELECTOR", "pixels can only be written to an image layer")
  end
  if frame_number < 1 or frame_number > #sprite.frames then
    fail("INVALID_SELECTOR", "frame index is outside the sprite")
  end

  local existing = layer:cel(frame_number)
  local image = Image(sprite.spec)
  if existing ~= nil then image:drawImage(existing.image, existing.position) end

  for _, pixel in ipairs(pixels) do
    if pixel.x < 0 or pixel.x >= sprite.width or pixel.y < 0 or pixel.y >= sprite.height then
      fail("INVALID_SELECTOR", "pixel coordinate is outside the sprite")
    end
    image:drawPixel(pixel.x, pixel.y, parse_color(pixel.color))
  end

  if existing ~= nil then
    existing.image = image
    existing.position = Point(0, 0)
  else
    sprite:newCel(layer, frame_number, image, Point(0, 0))
  end
end

local operations = {}

operations.health = function(_)
  return { aseprite_version = tostring(app.version), api_version = app.apiVersion or 0 }
end

operations.inspect = function(input)
  local sprite = open_sprite(input.source_path)
  local result = inspect_sprite(sprite, input.include_palette_colors == true, input.source_path)
  sprite:close()
  return result
end

operations.create = function(input)
  local modes = {
    rgb = ColorMode.RGB,
    grayscale = ColorMode.GRAY,
    indexed = ColorMode.INDEXED
  }
  local mode = modes[input.color_mode]
  if mode == nil then fail("UNSUPPORTED_FORMAT", "unsupported color mode") end

  local sprite = Sprite(input.width, input.height, mode)
  local layers = input.layers or {}
  if #layers > 0 then sprite.layers[1].name = layers[1].name end
  for index = 2, #layers do
    local layer = sprite:newLayer()
    layer.name = layers[index].name
  end

  local frames = input.frames or {}
  for _ = 2, #frames do sprite:newEmptyFrame() end
  for index, frame_input in ipairs(frames) do
    sprite.frames[index].duration = frame_input.duration_ms / 1000.0
  end

  local pixels = input.pixels or {}
  if #pixels > 0 then draw_pixels(sprite, sprite.layers[1], 1, pixels) end

  local saved = sprite:saveAs(input.output_path)
  if saved == false then fail("ASEPRITE_FAILED", "Aseprite could not save the document") end
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.set_pixels = function(input)
  local sprite = open_sprite(input.source_path)
  local layer = find_layer(sprite, input.layer)
  app.transaction("MCP set pixels", function()
    draw_pixels(sprite, layer, input.frame + 1, input.pixels)
  end)
  local saved = sprite:saveCopyAs(input.output_path)
  if saved == false then fail("ASEPRITE_FAILED", "Aseprite could not save the edited document") end
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

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
