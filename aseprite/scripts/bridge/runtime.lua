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

local function animation_direction_value(name)
  if name == "forward" then return AniDir.FORWARD end
  if name == "reverse" then return AniDir.REVERSE end
  if name == "ping_pong" then return AniDir.PING_PONG end
  if name == "ping_pong_reverse" then return AniDir.PING_PONG_REVERSE end
  fail("INVALID_INPUT", "unsupported animation direction")
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

  local animation_events = {}
  local encoded_events = sprite.properties["mcp.animation_events"]
  if type(encoded_events) == "string" and encoded_events ~= "" then
    local decoded, value = pcall(json.decode, encoded_events)
    if decoded and type(value) == "table" then animation_events = value end
  end

  return {
    source_path = source_path,
    width = sprite.width,
    height = sprite.height,
    color_mode = color_mode_name(sprite.colorMode),
    color_space = sprite.colorSpace and sprite.colorSpace.name or "",
    transparent_color = sprite.transparentColor,
    pixel_ratio = { width = sprite.pixelRatio.width, height = sprite.pixelRatio.height },
    grid = rectangle_info(sprite.gridBounds),
    frame_count = #sprite.frames,
    frames = frames,
    layers = layers,
    tags = tags,
    slices = slices,
    palettes = palettes,
    animation_events = animation_events
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

local function pixel_rgba(sprite, layer, pixel)
  if sprite.colorMode == ColorMode.RGB then
    return app.pixelColor.rgbaR(pixel), app.pixelColor.rgbaG(pixel),
      app.pixelColor.rgbaB(pixel), app.pixelColor.rgbaA(pixel)
  end
  if sprite.colorMode == ColorMode.GRAY then
    local value = app.pixelColor.grayaV(pixel)
    return value, value, value, app.pixelColor.grayaA(pixel)
  end
  if pixel == sprite.transparentColor and (layer == nil or not layer.isBackground) then
    return 0, 0, 0, 0
  end
  local palette = sprite.palettes[1]
  if palette == nil or pixel < 0 or pixel >= #palette then return 0, 0, 0, 255 end
  local color = palette:getColor(pixel)
  return color.red, color.green, color.blue, color.alpha
end

local function rgba_hex(red, green, blue, alpha)
  return string.format("#%02X%02X%02X%02X", red, green, blue, alpha)
end

local function find_tag(sprite, name)
  local found = nil
  for _, tag in ipairs(sprite.tags) do
    if tag.name == name then
      if found ~= nil then fail("INVALID_SELECTOR", "tag name is ambiguous: " .. name) end
      found = tag
    end
  end
  return found
end

local function count_layers(layers)
  local count = 0
  for _, layer in ipairs(layers) do
    count = count + 1
    if layer.isGroup then count = count + count_layers(layer.layers) end
  end
  return count
end

local function transformed_image(sprite, source, action)
  local rotated = action == "rotate_90_cw" or action == "rotate_90_ccw"
  local width = rotated and source.height or source.width
  local height = rotated and source.width or source.height
  local spec = ImageSpec {
    width = width,
    height = height,
    colorMode = sprite.colorMode,
    transparentColor = sprite.transparentColor
  }
  local target = Image(spec)
  target:clear()
  for y = 0, source.height - 1 do
    for x = 0, source.width - 1 do
      local target_x, target_y = x, y
      if action == "flip_horizontal" then target_x = source.width - 1 - x end
      if action == "flip_vertical" then target_y = source.height - 1 - y end
      if action == "rotate_90_cw" then
        target_x, target_y = source.height - 1 - y, x
      end
      if action == "rotate_90_ccw" then
        target_x, target_y = y, source.width - 1 - x
      end
      target:drawPixel(target_x, target_y, source:getPixel(x, y))
    end
  end
  return target
end

local function render_frame_image(sprite, frame_number)
  if frame_number < 1 or frame_number > #sprite.frames then
    fail("INVALID_SELECTOR", "frame index is outside the sprite")
  end
  local image = Image(sprite.spec)
  image:clear()
  image:drawSprite(sprite, frame_number, Point(0, 0))
  return image
end

local function read_image_runs(sprite, image, input)
  if input.x + input.width > image.width or input.y + input.height > image.height then
    fail("INVALID_SELECTOR", "pixel bounds extend outside the sprite")
  end
  local runs = {}
  local pixel_count = 0
  for y = input.y, input.y + input.height - 1 do
    local run_color, run_x, run_length = nil, nil, 0
    for x = input.x, input.x + input.width - 1 do
      local red, green, blue, alpha = pixel_rgba(sprite, nil, image:getPixel(x, y))
      local color = rgba_hex(red, green, blue, alpha)
      local included = input.include_transparent == true or alpha > 0
      if included then
        pixel_count = pixel_count + 1
        if run_color == color and run_x + run_length == x then
          run_length = run_length + 1
        else
          if run_color ~= nil then
            table.insert(runs, { x = run_x, y = y, length = run_length, color = run_color })
          end
          run_color, run_x, run_length = color, x, 1
        end
      elseif run_color ~= nil then
        table.insert(runs, { x = run_x, y = y, length = run_length, color = run_color })
        run_color, run_x, run_length = nil, nil, 0
      end
    end
    if run_color ~= nil then
      table.insert(runs, { x = run_x, y = y, length = run_length, color = run_color })
    end
  end
  return runs, pixel_count
end

local function find_slice(sprite, name)
  local found = nil
  for _, slice in ipairs(sprite.slices) do
    if slice.name == name then
      if found ~= nil then fail("INVALID_SELECTOR", "slice name is ambiguous: " .. name) end
      found = slice
    end
  end
  return found
end

local function find_tileset(sprite, name)
  local found = nil
  for _, tileset in ipairs(sprite.tilesets) do
    if tileset.name == name then
      if found ~= nil then fail("INVALID_SELECTOR", "tileset name is ambiguous: " .. name) end
      found = tileset
    end
  end
  if found == nil then fail("INVALID_SELECTOR", "tileset was not found: " .. name) end
  return found
end

local DIGITS = {
  ["0"] = { "111", "101", "101", "101", "111" },
  ["1"] = { "010", "110", "010", "010", "111" },
  ["2"] = { "111", "001", "111", "100", "111" },
  ["3"] = { "111", "001", "111", "001", "111" },
  ["4"] = { "101", "101", "111", "001", "001" },
  ["5"] = { "111", "100", "111", "001", "111" },
  ["6"] = { "111", "100", "111", "101", "111" },
  ["7"] = { "111", "001", "010", "010", "010" },
  ["8"] = { "111", "101", "111", "101", "111" },
  ["9"] = { "111", "101", "111", "001", "111" }
}

local function draw_number(image, number, x, y, color)
  local text = tostring(number)
  for character_index = 1, #text do
    local glyph = DIGITS[string.sub(text, character_index, character_index)]
    for row = 1, 5 do
      for column = 1, 3 do
        if string.sub(glyph[row], column, column) == "1" then
          image:drawPixel(x + (character_index - 1) * 4 + column - 1, y + row - 1, color)
        end
      end
    end
  end
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
