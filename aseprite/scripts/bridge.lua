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

local function save_copy(sprite, output_path)
  local saved = sprite:saveCopyAs(output_path)
  if saved == false then fail("ASEPRITE_FAILED", "Aseprite could not save the edited document") end
end

local function anchor_offset(anchor, delta_x, delta_y)
  local horizontal = 0.5
  local vertical = 0.5
  if string.find(anchor, "left", 1, true) ~= nil then horizontal = 0 end
  if string.find(anchor, "right", 1, true) ~= nil then horizontal = 1 end
  if string.find(anchor, "top", 1, true) ~= nil then vertical = 0 end
  if string.find(anchor, "bottom", 1, true) ~= nil then vertical = 1 end
  return math.floor(delta_x * horizontal), math.floor(delta_y * vertical)
end

local function pixel_alpha(sprite, layer, pixel)
  if sprite.colorMode == ColorMode.RGB then return app.pixelColor.rgbaA(pixel) end
  if sprite.colorMode == ColorMode.GRAY then return app.pixelColor.grayaA(pixel) end
  if layer.isBackground then return 255 end
  if pixel == sprite.transparentColor then return 0 end
  local palette = sprite.palettes[1]
  if palette == nil or pixel < 0 or pixel >= #palette then return 255 end
  return palette:getColor(pixel).alpha
end

local function visible_layer(layer)
  local current = layer
  while current ~= nil and current.name ~= nil do
    if current.isVisible == false then return false end
    if current.opacity ~= nil and current.opacity == 0 then return false end
    current = current.parent
  end
  return true
end

local function validate_animation(sprite, input)
  local maximum_visits = input.max_pixel_visits or 16777216
  local visits = 0
  local frame_bounds = {}
  local empty_frames = {}
  local signatures = {}
  local durations = {}
  local baselines = {}
  local widths = {}
  local heights = {}
  local used_tilemap_approximation = false

  for frame_index, frame in ipairs(sprite.frames) do
    local min_x, min_y = sprite.width, sprite.height
    local max_x, max_y = -1, -1
    local opaque_pixels = 0
    local checksum = 0
    table.insert(durations, math.floor(frame.duration * 1000 + 0.5))

    for _, cel in ipairs(sprite.cels) do
      if cel.frame.frameNumber == frame_index and visible_layer(cel.layer) and cel.opacity > 0 then
        local image = cel.image
        visits = visits + image.width * image.height
        if visits > maximum_visits then
          fail("LIMIT_EXCEEDED", "animation validation exceeded the pixel-visit limit")
        end
        if cel.layer.isTilemap then
          used_tilemap_approximation = true
          local bounds = cel.bounds
          local clipped_min_x = math.max(0, bounds.x)
          local clipped_min_y = math.max(0, bounds.y)
          local clipped_max_x = math.min(sprite.width - 1, bounds.x + bounds.width - 1)
          local clipped_max_y = math.min(sprite.height - 1, bounds.y + bounds.height - 1)
          if clipped_max_x >= clipped_min_x and clipped_max_y >= clipped_min_y then
            min_x, min_y = math.min(min_x, clipped_min_x), math.min(min_y, clipped_min_y)
            max_x, max_y = math.max(max_x, clipped_max_x), math.max(max_y, clipped_max_y)
            opaque_pixels = opaque_pixels +
              (clipped_max_x - clipped_min_x + 1) * (clipped_max_y - clipped_min_y + 1)
            checksum = (checksum + bounds.x * 31 + bounds.y * 131 +
              bounds.width * 521 + bounds.height * 2053) % 2147483647
          end
        else
          for y = 0, image.height - 1 do
            for x = 0, image.width - 1 do
              local pixel = image:getPixel(x, y)
              if pixel_alpha(sprite, cel.layer, pixel) > 0 then
                local absolute_x = cel.position.x + x
                local absolute_y = cel.position.y + y
                if absolute_x >= 0 and absolute_x < sprite.width and
                  absolute_y >= 0 and absolute_y < sprite.height then
                  min_x, min_y = math.min(min_x, absolute_x), math.min(min_y, absolute_y)
                  max_x, max_y = math.max(max_x, absolute_x), math.max(max_y, absolute_y)
                  opaque_pixels = opaque_pixels + 1
                  checksum = (checksum * 65599 + pixel + absolute_x * 31 + absolute_y * 131)
                    % 2147483647
                end
              end
            end
          end
        end
      end
    end

    local bounds = nil
    local baseline = nil
    if opaque_pixels == 0 then
      table.insert(empty_frames, frame_index - 1)
    else
      local width, height = max_x - min_x + 1, max_y - min_y + 1
      bounds = { x = min_x, y = min_y, width = width, height = height }
      baseline = max_y
      table.insert(baselines, baseline)
      table.insert(widths, width)
      table.insert(heights, height)
      local key = table.concat({opaque_pixels, min_x, min_y, max_x, max_y, checksum}, ":")
      if signatures[key] == nil then signatures[key] = {} end
      table.insert(signatures[key], frame_index - 1)
    end
    table.insert(frame_bounds, {
      frame = frame_index - 1,
      bounds = bounds,
      opaque_pixels = opaque_pixels,
      baseline = baseline
    })
  end

  local function drift(values)
    if #values < 2 then return 0 end
    local minimum, maximum = values[1], values[1]
    for index = 2, #values do
      minimum, maximum = math.min(minimum, values[index]), math.max(maximum, values[index])
    end
    return maximum - minimum
  end

  local duplicate_groups = {}
  if input.check_duplicates == true then
    for _, frames in pairs(signatures) do
      if #frames > 1 then table.insert(duplicate_groups, frames) end
    end
    table.sort(duplicate_groups, function(a, b) return a[1] < b[1] end)
  end

  local baseline_drift = drift(baselines)
  local width_drift = drift(widths)
  local height_drift = drift(heights)
  local issues = {}
  if #empty_frames > 0 then
    table.insert(issues, {
      code = "EMPTY_FRAMES", severity = "error",
      message = "One or more animation frames contain no visible pixels", frames = empty_frames
    })
  end
  if baseline_drift > input.baseline_tolerance then
    table.insert(issues, {
      code = "BASELINE_DRIFT", severity = "warning",
      message = "Frame baselines differ by more than the configured tolerance", frames = {}
    })
  end
  if width_drift > input.bounds_tolerance then
    table.insert(issues, {
      code = "WIDTH_DRIFT", severity = "warning",
      message = "Visible frame widths differ by more than the configured tolerance", frames = {}
    })
  end
  if height_drift > input.bounds_tolerance then
    table.insert(issues, {
      code = "HEIGHT_DRIFT", severity = "warning",
      message = "Visible frame heights differ by more than the configured tolerance", frames = {}
    })
  end
  for _, frames in ipairs(duplicate_groups) do
    table.insert(issues, {
      code = "DUPLICATE_FRAMES", severity = "warning",
      message = "Frames have matching visible-pixel signatures", frames = frames
    })
  end
  if used_tilemap_approximation then
    table.insert(issues, {
      code = "TILEMAP_BOUNDS_APPROXIMATED", severity = "warning",
      message = "Tilemap cels were validated using cel bounds", frames = {}
    })
  end

  return {
    width = sprite.width,
    height = sprite.height,
    frame_count = #sprite.frames,
    durations_ms = durations,
    frame_bounds = frame_bounds,
    empty_frames = empty_frames,
    duplicate_groups = duplicate_groups,
    baseline_drift = baseline_drift,
    bounds_width_drift = width_drift,
    bounds_height_drift = height_drift,
    issues = issues,
    valid = #issues == 0
  }
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

operations.import_sprite_sheet = function(input)
  local source = open_sprite(input.source_path)
  if #source.cels == 0 then
    source:close()
    fail("INVALID_SPRITE", "sprite sheet does not contain an image cel")
  end
  local source_cel = source.cels[1]
  local source_image = source_cel.image
  local margin = input.margin or 0
  local spacing = input.spacing or 0
  local cell_step_x = input.frame_width + spacing
  local cell_step_y = input.frame_height + spacing
  local available_width = source.width - margin * 2
  local available_height = source.height - margin * 2
  local available_columns = math.floor((available_width + spacing) / cell_step_x)
  local available_rows = math.floor((available_height + spacing) / cell_step_y)
  local columns = input.columns or available_columns
  if available_columns < 1 or available_rows < 1 or columns < 1 or columns > available_columns then
    source:close()
    fail("INVALID_INPUT", "frame grid does not fit inside the source PNG")
  end
  local capacity = columns * available_rows
  local frame_count = input.frame_count or capacity
  if frame_count < 1 or frame_count > capacity then
    source:close()
    fail("INVALID_INPUT", "frame_count exceeds the complete cells in the source PNG")
  end
  if frame_count > input.max_frames then
    source:close()
    fail("LIMIT_EXCEEDED", "sprite-sheet frame count exceeds the limit")
  end
  if frame_count * input.frame_width * input.frame_height > input.max_total_pixels then
    source:close()
    fail("LIMIT_EXCEEDED", "sprite-sheet animation pixel count exceeds the limit")
  end

  local color_key = nil
  if input.transparent_color ~= nil then color_key = parse_color(input.transparent_color) end
  local match_key_alpha = input.transparent_color ~= nil and
    string.len(input.transparent_color) == 9
  local sprite = Sprite(input.frame_width, input.frame_height, ColorMode.RGB)
  sprite.layers[1].name = input.layer_name
  for index = 1, frame_count do
    local zero_index = index - 1
    local column = zero_index % columns
    local row = math.floor(zero_index / columns)
    local source_x = margin + column * cell_step_x
    local source_y = margin + row * cell_step_y
    local image = Image(sprite.spec)
    image:clear()
    image:drawImage(
      source_image,
      Point(source_cel.position.x - source_x, source_cel.position.y - source_y)
    )
    if color_key ~= nil then
      for y = 0, image.height - 1 do
        for x = 0, image.width - 1 do
          local pixel = image:getPixel(x, y)
          if app.pixelColor.rgbaR(pixel) == color_key.red and
            app.pixelColor.rgbaG(pixel) == color_key.green and
            app.pixelColor.rgbaB(pixel) == color_key.blue and
            (not match_key_alpha or app.pixelColor.rgbaA(pixel) == color_key.alpha) then
            image:drawPixel(x, y, Color { r = 0, g = 0, b = 0, a = 0 })
          end
        end
      end
    end
    local frame
    if index == 1 then
      frame = sprite.frames[1]
      sprite.cels[1].image = image
    else
      frame = sprite:newEmptyFrame()
      if frame == nil then frame = sprite.frames[#sprite.frames] end
      sprite:newCel(sprite.layers[1], frame, image, Point(0, 0))
    end
    frame.duration = input.duration_ms / 1000.0
  end
  if input.tag_name ~= nil then
    local tag = sprite:newTag(1, frame_count)
    tag.name = input.tag_name
  end
  local saved = sprite:saveAs(input.output_path)
  if saved == false then
    source:close()
    sprite:close()
    fail("ASEPRITE_FAILED", "Aseprite could not save the imported sprite sheet")
  end
  local result = inspect_sprite(sprite, false, input.output_path)
  source:close()
  sprite:close()
  return result
end

operations.resize_canvas = function(input)
  local sprite = open_sprite(input.source_path)
  local delta_x = input.width - sprite.width
  local delta_y = input.height - sprite.height
  local offset_x, offset_y = anchor_offset(input.anchor, delta_x, delta_y)
  app.transaction("MCP resize canvas", function()
    sprite:crop(Rectangle(-offset_x, -offset_y, input.width, input.height))
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.resize_sprite = function(input)
  if input.method ~= "nearest" then fail("INVALID_INPUT", "unsupported resize method") end
  local sprite = open_sprite(input.source_path)
  app.transaction("MCP resize sprite", function()
    app.command.SpriteSize {
      ui = false,
      width = input.width,
      height = input.height,
      lockRatio = false,
      method = input.method
    }
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.validate_animation = function(input)
  local sprite = open_sprite(input.source_path)
  local result = validate_animation(sprite, input)
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
