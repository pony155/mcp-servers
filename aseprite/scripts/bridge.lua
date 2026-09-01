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

operations.create_animation = function(input)
  local modes = {
    rgb = ColorMode.RGB,
    grayscale = ColorMode.GRAY,
    indexed = ColorMode.INDEXED
  }
  local mode = modes[input.color_mode]
  if mode == nil then fail("UNSUPPORTED_FORMAT", "unsupported color mode") end

  local sprite = Sprite(input.width, input.height, mode)
  local layers = input.layers or {}
  sprite.layers[1].name = layers[1].name
  for index = 2, #layers do
    local layer = sprite:newLayer()
    layer.name = layers[index].name
  end

  local frames = input.frames or {}
  for _ = 2, #frames do sprite:newEmptyFrame() end
  app.transaction("MCP create animation", function()
    for frame_index, frame_input in ipairs(frames) do
      sprite.frames[frame_index].duration = frame_input.duration_ms / 1000.0
      for _, cel_input in ipairs(frame_input.cels or {}) do
        local layer = find_layer(sprite, cel_input.layer)
        draw_pixels(sprite, layer, frame_index, cel_input.pixels)
      end
    end
    for _, tag_input in ipairs(input.tags or {}) do
      local tag = sprite:newTag(tag_input.from_frame + 1, tag_input.to_frame + 1)
      tag.name = tag_input.name
      tag.aniDir = animation_direction_value(tag_input.direction)
      tag.repeats = tag_input.repeats
    end
  end)

  local saved = sprite:saveAs(input.output_path)
  if saved == false then fail("ASEPRITE_FAILED", "Aseprite could not save the animation") end
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

operations.read_pixels = function(input)
  local sprite = open_sprite(input.source_path)
  local layer = find_layer(sprite, input.layer)
  if layer.isGroup or layer.isTilemap then
    sprite:close()
    fail("INVALID_SELECTOR", "pixels can only be read from an image layer")
  end
  local frame_number = input.frame + 1
  if frame_number < 1 or frame_number > #sprite.frames then
    sprite:close()
    fail("INVALID_SELECTOR", "frame index is outside the sprite")
  end
  if input.x + input.width > sprite.width or input.y + input.height > sprite.height then
    sprite:close()
    fail("INVALID_SELECTOR", "pixel bounds extend outside the sprite")
  end
  local cel = layer:cel(frame_number)
  local runs = {}
  local pixel_count = 0
  for y = input.y, input.y + input.height - 1 do
    local run_color, run_x, run_length = nil, nil, 0
    for x = input.x, input.x + input.width - 1 do
      local red, green, blue, alpha = 0, 0, 0, 0
      if cel ~= nil then
        local image_x = x - cel.position.x
        local image_y = y - cel.position.y
        if image_x >= 0 and image_x < cel.image.width and image_y >= 0 and image_y < cel.image.height then
          red, green, blue, alpha = pixel_rgba(sprite, layer, cel.image:getPixel(image_x, image_y))
        end
      end
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
      else
        if run_color ~= nil then
          table.insert(runs, { x = run_x, y = y, length = run_length, color = run_color })
          run_color, run_x, run_length = nil, nil, 0
        end
      end
    end
    if run_color ~= nil then
      table.insert(runs, { x = run_x, y = y, length = run_length, color = run_color })
    end
  end
  local result = {
    layer = input.layer,
    frame = input.frame,
    bounds = { x = input.x, y = input.y, width = input.width, height = input.height },
    encoding = "rgba_runs",
    runs = runs,
    pixel_count = pixel_count
  }
  sprite:close()
  return result
end

operations.edit_frames = function(input)
  local sprite = open_sprite(input.source_path)
  app.transaction("MCP edit frames", function()
    for _, operation in ipairs(input.operations or {}) do
      local frame_number = operation.frame + 1
      if operation.action == "add" then
        if operation.frame > #sprite.frames then fail("INVALID_SELECTOR", "frame insertion index is outside the sprite") end
        sprite:newEmptyFrame(frame_number)
      else
        if frame_number < 1 or frame_number > #sprite.frames then fail("INVALID_SELECTOR", "frame index is outside the sprite") end
        if operation.action == "duplicate" then
          sprite:newFrame(frame_number)
        elseif operation.action == "remove" then
          if #sprite.frames == 1 then fail("INVALID_INPUT", "the only frame cannot be removed") end
          sprite:deleteFrame(sprite.frames[frame_number])
        elseif operation.action == "set_duration" then
          sprite.frames[frame_number].duration = operation.duration_ms / 1000.0
        else
          fail("INVALID_INPUT", "unsupported frame edit action")
        end
      end
      if #sprite.frames > input.max_frames then fail("LIMIT_EXCEEDED", "frame count exceeds the limit") end
    end
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.edit_layers = function(input)
  local sprite = open_sprite(input.source_path)
  app.transaction("MCP edit layers", function()
    for _, operation in ipairs(input.operations or {}) do
      local action = operation.action
      if action == "add" or action == "add_group" then
        local layer = action == "add" and sprite:newLayer() or sprite:newGroup()
        layer.name = operation.name
        if operation.parent ~= nil then
          local parent = find_layer(sprite, operation.parent)
          if not parent.isGroup then fail("INVALID_SELECTOR", "parent must be a group layer") end
          layer.parent = parent
        end
      else
        local layer = find_layer(sprite, operation.layer)
        if action == "remove" then
          sprite:deleteLayer(layer)
        elseif action == "rename" then
          layer.name = operation.name
        elseif action == "set_visibility" then
          layer.isVisible = operation.visible
        elseif action == "set_opacity" then
          if layer.isGroup then fail("INVALID_SELECTOR", "group layers do not have opacity") end
          layer.opacity = operation.opacity
        elseif action == "move" then
          if operation.parent ~= nil then
            local parent = find_layer(sprite, operation.parent)
            if not parent.isGroup then fail("INVALID_SELECTOR", "parent must be a group layer") end
            layer.parent = parent
          end
          if operation.stack_index ~= nil then layer.stackIndex = operation.stack_index end
        else
          fail("INVALID_INPUT", "unsupported layer edit action")
        end
      end
      if count_layers(sprite.layers) > input.max_layers then fail("LIMIT_EXCEEDED", "layer count exceeds the limit") end
    end
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.edit_tags = function(input)
  local sprite = open_sprite(input.source_path)
  app.transaction("MCP edit tags", function()
    for _, operation in ipairs(input.operations or {}) do
      local tag = find_tag(sprite, operation.name)
      if operation.action == "remove" then
        if tag == nil then fail("INVALID_SELECTOR", "tag was not found: " .. operation.name) end
        sprite:deleteTag(tag)
      elseif operation.action == "set" then
        if operation.to_frame >= #sprite.frames then fail("INVALID_SELECTOR", "tag frame range is outside the sprite") end
        local direction = tag ~= nil and tag.aniDir or AniDir.FORWARD
        local repeats = tag ~= nil and tag.repeats or 0
        if tag ~= nil then sprite:deleteTag(tag) end
        tag = sprite:newTag(operation.from_frame + 1, operation.to_frame + 1)
        tag.name = operation.name
        tag.aniDir = operation.direction ~= nil and
          animation_direction_value(operation.direction) or direction
        tag.repeats = operation.repeats ~= nil and operation.repeats or repeats
      else
        fail("INVALID_INPUT", "unsupported tag edit action")
      end
    end
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.apply_palette = function(input)
  local sprite = open_sprite(input.source_path)
  if sprite.colorMode == ColorMode.GRAY then
    sprite:close()
    fail("UNSUPPORTED_FORMAT", "palette application does not support grayscale sprites")
  end
  local colors = {}
  for _, value in ipairs(input.colors or {}) do table.insert(colors, parse_color(value)) end
  local visits = 0
  app.transaction("MCP apply palette", function()
    if sprite.colorMode == ColorMode.INDEXED then
      if #colors > 255 then fail("LIMIT_EXCEEDED", "indexed palettes allow 255 colors plus transparency") end
      local old_palette = sprite.palettes[1]
      local old_transparent = sprite.transparentColor
      local old_colors = {}
      for index = 0, #old_palette - 1 do old_colors[index] = old_palette:getColor(index) end
      for _, cel in ipairs(sprite.cels) do
        if not cel.layer.isTilemap then
          local image = Image(cel.image)
          for y = 0, image.height - 1 do
            for x = 0, image.width - 1 do
              visits = visits + 1
              if visits > input.max_pixel_visits then fail("LIMIT_EXCEEDED", "palette operation exceeds the pixel visit limit") end
              local pixel = image:getPixel(x, y)
              if pixel ~= old_transparent or cel.layer.isBackground then
                local source = old_colors[pixel] or Color { r = 0, g = 0, b = 0, a = 255 }
                local best, distance = 0, nil
                for index, target in ipairs(colors) do
                  local delta_r, delta_g, delta_b = source.red - target.red, source.green - target.green, source.blue - target.blue
                  local candidate = delta_r * delta_r + delta_g * delta_g + delta_b * delta_b
                  if distance == nil or candidate < distance then best, distance = index, candidate end
                end
                image:drawPixel(x, y, best)
              else
                image:drawPixel(x, y, 0)
              end
            end
          end
          cel.image = image
        end
      end
      local palette = Palette(#colors + 1)
      palette:setColor(0, Color { r = 0, g = 0, b = 0, a = 0 })
      for index, color in ipairs(colors) do palette:setColor(index, color) end
      sprite:setPalette(palette)
      sprite.transparentColor = 0
    else
      for _, cel in ipairs(sprite.cels) do
        if not cel.layer.isTilemap then
          local image = Image(cel.image)
          for y = 0, image.height - 1 do
            for x = 0, image.width - 1 do
              visits = visits + 1
              if visits > input.max_pixel_visits then fail("LIMIT_EXCEEDED", "palette operation exceeds the pixel visit limit") end
              local pixel = image:getPixel(x, y)
              local red, green, blue, alpha = pixel_rgba(sprite, cel.layer, pixel)
              if alpha > 0 then
                local best, distance = colors[1], nil
                for _, target in ipairs(colors) do
                  local delta_r, delta_g, delta_b = red - target.red, green - target.green, blue - target.blue
                  local candidate = delta_r * delta_r + delta_g * delta_g + delta_b * delta_b
                  if distance == nil or candidate < distance then best, distance = target, candidate end
                end
                local output_alpha = input.preserve_alpha == true and alpha or best.alpha
                image:drawPixel(x, y, Color { r = best.red, g = best.green, b = best.blue, a = output_alpha })
              end
            end
          end
          cel.image = image
        end
      end
    end
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.transform_cel = function(input)
  local sprite = open_sprite(input.source_path)
  local layer = find_layer(sprite, input.layer)
  if layer.isGroup or layer.isTilemap then
    sprite:close()
    fail("INVALID_SELECTOR", "cel transforms require an image layer")
  end
  local frame_number = input.frame + 1
  if frame_number < 1 or frame_number > #sprite.frames then
    sprite:close()
    fail("INVALID_SELECTOR", "frame index is outside the sprite")
  end
  local cel = layer:cel(frame_number)
  if cel == nil then
    sprite:close()
    fail("INVALID_SELECTOR", "the selected layer and frame do not contain a cel")
  end
  app.transaction("MCP transform cel", function()
    if input.action == "translate" then
      cel.position = Point(cel.position.x + input.offset_x, cel.position.y + input.offset_y)
    elseif input.action == "flip_horizontal" or input.action == "flip_vertical" or
      input.action == "rotate_90_cw" or input.action == "rotate_90_ccw" then
      cel.image = transformed_image(sprite, cel.image, input.action)
    else
      fail("INVALID_INPUT", "unsupported cel transform action")
    end
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.read_composited_pixels = function(input)
  local sprite = open_sprite(input.source_path)
  local image = render_frame_image(sprite, input.frame + 1)
  local runs, pixel_count = read_image_runs(sprite, image, input)
  local result = {
    frame = input.frame,
    bounds = { x = input.x, y = input.y, width = input.width, height = input.height },
    encoding = "rgba_runs",
    runs = runs,
    pixel_count = pixel_count
  }
  sprite:close()
  return result
end

operations.set_pixel_runs = function(input)
  local sprite = open_sprite(input.source_path)
  local layer = find_layer(sprite, input.layer)
  if layer.isGroup or layer.isTilemap then
    sprite:close()
    fail("INVALID_SELECTOR", "pixel runs require an image layer")
  end
  local frame_number = input.frame + 1
  if frame_number < 1 or frame_number > #sprite.frames then
    sprite:close()
    fail("INVALID_SELECTOR", "frame index is outside the sprite")
  end
  app.transaction("MCP set pixel runs", function()
    local existing = layer:cel(frame_number)
    local image = Image(sprite.spec)
    if existing ~= nil then image:drawImage(existing.image, existing.position) end
    for _, run in ipairs(input.runs or {}) do
      if run.x + run.length > sprite.width or run.y >= sprite.height then
        fail("INVALID_SELECTOR", "pixel run extends outside the sprite")
      end
      local color = parse_color(run.color)
      for x = run.x, run.x + run.length - 1 do image:drawPixel(x, run.y, color) end
    end
    if existing ~= nil then
      existing.image = image
      existing.position = Point(0, 0)
    else
      sprite:newCel(layer, frame_number, image, Point(0, 0))
    end
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.copy_cel = function(input)
  local sprite = open_sprite(input.source_path)
  local source_layer = find_layer(sprite, input.source_layer)
  local target_layer = find_layer(sprite, input.target_layer)
  if source_layer.isGroup or source_layer.isTilemap or target_layer.isGroup or target_layer.isTilemap then
    sprite:close()
    fail("INVALID_SELECTOR", "cel copying requires image layers")
  end
  local source_frame = input.source_frame + 1
  local target_frame = input.target_frame + 1
  if source_frame < 1 or source_frame > #sprite.frames or target_frame < 1 or target_frame > #sprite.frames then
    sprite:close()
    fail("INVALID_SELECTOR", "frame index is outside the sprite")
  end
  local source_cel = source_layer:cel(source_frame)
  if source_cel == nil then
    sprite:close()
    fail("INVALID_SELECTOR", "source cel does not exist")
  end
  local target_cel = target_layer:cel(target_frame)
  if target_cel ~= nil and input.replace ~= true then
    sprite:close()
    fail("OUTPUT_EXISTS", "target cel exists; set replace=true to replace it")
  end
  app.transaction("MCP copy cel", function()
    if target_cel ~= nil then sprite:deleteCel(target_cel) end
    local image = input.linked == true and source_cel.image or Image(source_cel.image)
    local copied = sprite:newCel(target_layer, target_frame, image, source_cel.position)
    copied.opacity = source_cel.opacity
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.trim_cels = function(input)
  local sprite = open_sprite(input.source_path)
  local selected_layers = {}
  if #(input.layers or {}) == 0 then
    for _, layer in ipairs(sprite.layers) do
      if not layer.isGroup and not layer.isTilemap then selected_layers[layer] = true end
    end
    local function add_children(layers)
      for _, layer in ipairs(layers) do
        if layer.isGroup then add_children(layer.layers)
        elseif not layer.isTilemap then selected_layers[layer] = true end
      end
    end
    add_children(sprite.layers)
  else
    for _, path in ipairs(input.layers) do
      local layer = find_layer(sprite, path)
      if layer.isGroup or layer.isTilemap then fail("INVALID_SELECTOR", "trim requires image layers") end
      selected_layers[layer] = true
    end
  end
  local selected_frames = {}
  if #(input.frames or {}) == 0 then
    for index = 1, #sprite.frames do selected_frames[index] = true end
  else
    for _, index in ipairs(input.frames) do
      if index >= #sprite.frames then fail("INVALID_SELECTOR", "frame index is outside the sprite") end
      selected_frames[index + 1] = true
    end
  end
  local trim_cache = {}
  app.transaction("MCP trim cels", function()
    local cels = {}
    for _, cel in ipairs(sprite.cels) do table.insert(cels, cel) end
    for _, cel in ipairs(cels) do
      if selected_layers[cel.layer] and selected_frames[cel.frame.frameNumber] then
        local image_id = cel.image.id
        local cached = trim_cache[image_id]
        local bounds = cached ~= nil and cached.bounds or cel.image:shrinkBounds()
        if bounds.width < 1 or bounds.height < 1 then
          trim_cache[image_id] = { bounds = bounds }
          if input.remove_empty == true and not cel.layer.isBackground then sprite:deleteCel(cel) end
        elseif bounds.width ~= cel.image.width or bounds.height ~= cel.image.height then
          local trimmed = cached ~= nil and cached.image or Image(cel.image, bounds)
          trim_cache[image_id] = { bounds = bounds, image = trimmed }
          cel.image = trimmed
          cel.position = Point(cel.position.x + bounds.x, cel.position.y + bounds.y)
        end
      end
    end
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.edit_slices = function(input)
  local sprite = open_sprite(input.source_path)
  app.transaction("MCP edit slices", function()
    for _, operation in ipairs(input.operations or {}) do
      local slice = find_slice(sprite, operation.name)
      if operation.action == "remove" then
        if slice == nil then fail("INVALID_SELECTOR", "slice was not found: " .. operation.name) end
        sprite:deleteSlice(slice)
      elseif operation.action == "set" then
        if operation.frame >= #sprite.frames then fail("INVALID_SELECTOR", "slice frame is outside the sprite") end
        app.frame = sprite.frames[operation.frame + 1]
        local bounds = Rectangle(operation.bounds.x, operation.bounds.y,
          operation.bounds.width, operation.bounds.height)
        if slice == nil then slice = sprite:newSlice(bounds) else slice.bounds = bounds end
        slice.name = operation.name
        if operation.center ~= nil then
          slice.center = Rectangle(operation.center.x, operation.center.y,
            operation.center.width, operation.center.height)
        else
          slice.center = nil
        end
        if operation.pivot ~= nil then
          slice.pivot = Point(operation.pivot.x, operation.pivot.y)
        else
          slice.pivot = nil
        end
      else
        fail("INVALID_INPUT", "unsupported slice edit action")
      end
    end
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.edit_properties = function(input)
  local sprite = open_sprite(input.source_path)
  app.transaction("MCP edit properties", function()
    for _, operation in ipairs(input.operations or {}) do
      local target = sprite
      if operation.target == "layer" then
        target = find_layer(sprite, operation.layer)
      elseif operation.target == "tag" then
        target = find_tag(sprite, operation.name)
      elseif operation.target == "slice" then
        target = find_slice(sprite, operation.name)
      elseif operation.target == "cel" then
        local layer = find_layer(sprite, operation.layer)
        if operation.frame >= #sprite.frames then fail("INVALID_SELECTOR", "cel frame is outside the sprite") end
        target = layer:cel(operation.frame + 1)
      elseif operation.target ~= "sprite" then
        fail("INVALID_INPUT", "unsupported property target")
      end
      if target == nil then fail("INVALID_SELECTOR", "property target was not found") end
      if operation.action == "set" then
        target.properties[operation.key] = operation.value
      elseif operation.action == "remove" then
        target.properties[operation.key] = nil
      else
        fail("INVALID_INPUT", "unsupported property edit action")
      end
    end
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.convert_color_mode = function(input)
  local sprite = open_sprite(input.source_path)
  local formats = { rgb = "rgb", grayscale = "gray", indexed = "indexed" }
  local format = formats[input.color_mode]
  if format == nil then fail("INVALID_INPUT", "unsupported color mode") end
  app.transaction("MCP convert color mode", function()
    local options = { ui = false, format = format }
    if input.dithering ~= "none" then
      options.dithering = input.dithering
      if input.dithering == "ordered" then
        options["dithering-matrix"] = input.dithering_matrix
      end
    else
      options.dithering = "none"
    end
    local changed = app.command.ChangePixelFormat(options)
    if changed == false then fail("ASEPRITE_FAILED", "Aseprite could not convert the color mode") end
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.edit_tileset = function(input)
  local sprite = open_sprite(input.source_path)
  app.transaction("MCP edit tileset", function()
    for _, operation in ipairs(input.operations or {}) do
      if operation.action == "add" then
        local tileset = sprite:newTileset(Rectangle(0, 0, operation.tile_width, operation.tile_height))
        tileset.name = operation.name
      else
        local tileset = find_tileset(sprite, operation.tileset)
        if operation.action == "rename" then
          tileset.name = operation.name
        elseif operation.action == "remove_tile" then
          if tileset:tile(operation.tile_index) == nil then fail("INVALID_SELECTOR", "tile was not found") end
          sprite:deleteTile(tileset, operation.tile_index)
        elseif operation.action == "add_tile" or operation.action == "set_tile_pixels" then
          local tile
          if operation.action == "add_tile" then
            tile = operation.tile_index ~= nil and
              sprite:newTile(tileset, operation.tile_index) or sprite:newTile(tileset)
          else
            tile = tileset:tile(operation.tile_index)
            if tile == nil then fail("INVALID_SELECTOR", "tile was not found") end
          end
          local size = tileset.grid.tileSize
          local spec = ImageSpec {
            width = size.width,
            height = size.height,
            colorMode = sprite.colorMode,
            transparentColor = sprite.transparentColor
          }
          local image = operation.action == "set_tile_pixels" and Image(tile.image) or Image(spec)
          for _, pixel in ipairs(operation.pixels or {}) do
            if pixel.x >= size.width or pixel.y >= size.height then
              fail("INVALID_SELECTOR", "tile pixel is outside the tile")
            end
            image:drawPixel(pixel.x, pixel.y, parse_color(pixel.color))
          end
          tile.image = image
        else
          fail("INVALID_INPUT", "unsupported tileset edit action")
        end
      end
    end
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.compare_frames = function(input)
  local sprite = open_sprite(input.source_path)
  local first = render_frame_image(sprite, input.first_frame + 1)
  local second = render_frame_image(sprite, input.second_frame + 1)
  if sprite.width * sprite.height > input.max_pixel_visits then
    sprite:close()
    fail("LIMIT_EXCEEDED", "frame comparison exceeds the pixel visit limit")
  end
  local changed = 0
  local min_x, min_y, max_x, max_y = sprite.width, sprite.height, -1, -1
  local first_baseline, second_baseline = nil, nil
  local difference = nil
  if input.difference_output_path ~= nil then
    difference = Image(sprite.width, sprite.height, ColorMode.RGB)
    difference:clear()
  end
  for y = 0, sprite.height - 1 do
    for x = 0, sprite.width - 1 do
      local first_pixel = first:getPixel(x, y)
      local second_pixel = second:getPixel(x, y)
      local _, _, _, first_alpha = pixel_rgba(sprite, nil, first_pixel)
      local _, _, _, second_alpha = pixel_rgba(sprite, nil, second_pixel)
      if first_alpha > 0 then first_baseline = y end
      if second_alpha > 0 then second_baseline = y end
      if first_pixel ~= second_pixel then
        changed = changed + 1
        min_x, min_y = math.min(min_x, x), math.min(min_y, y)
        max_x, max_y = math.max(max_x, x), math.max(max_y, y)
        if difference ~= nil then
          difference:drawPixel(x, y, app.pixelColor.rgba(255, 0, 255, 255))
        end
      end
    end
  end
  if difference ~= nil then difference:saveAs(input.difference_output_path) end
  local bounds = nil
  if changed > 0 then
    bounds = { x = min_x, y = min_y, width = max_x - min_x + 1, height = max_y - min_y + 1 }
  end
  local baseline_delta = nil
  if first_baseline ~= nil and second_baseline ~= nil then
    baseline_delta = second_baseline - first_baseline
  end
  local result = {
    first_frame = input.first_frame,
    second_frame = input.second_frame,
    changed_pixel_count = changed,
    changed_bounds = bounds,
    first_baseline = first_baseline,
    second_baseline = second_baseline,
    baseline_delta = baseline_delta
  }
  sprite:close()
  return result
end

operations.render_contact_sheet = function(input)
  local sprite = open_sprite(input.source_path)
  local frame_count = #sprite.frames
  local columns = math.min(input.columns, frame_count)
  local rows = math.ceil(frame_count / columns)
  local cell_width = sprite.width * input.scale + 2
  local cell_height = sprite.height * input.scale + 9
  local sheet_width = columns * cell_width
  local sheet_height = rows * cell_height
  if sheet_width * sheet_height > input.max_pixels then
    sprite:close()
    fail("LIMIT_EXCEEDED", "contact sheet exceeds the pixel limit")
  end
  local sheet = Image(sheet_width, sheet_height, ColorMode.RGB)
  sheet:clear(Rectangle(0, 0, sheet_width, sheet_height), Color { r = 32, g = 35, b = 42 })
  local label_color = app.pixelColor.rgba(230, 230, 230, 255)
  for frame_index = 1, #sprite.frames do
    local zero_index = frame_index - 1
    local column = zero_index % columns
    local row = math.floor(zero_index / columns)
    local origin_x = column * cell_width + 1
    local origin_y = row * cell_height
    draw_number(sheet, zero_index, origin_x, origin_y + 1, label_color)
    local frame_image = Image(sprite.width, sprite.height, ColorMode.RGB)
    frame_image:clear()
    frame_image:drawSprite(sprite, frame_index, Point(0, 0))
    if input.scale ~= 1 then
      frame_image:resize(sprite.width * input.scale, sprite.height * input.scale)
    end
    sheet:drawImage(frame_image, Point(origin_x, origin_y + 7))
  end
  sheet:saveAs(input.output_path)
  sprite:close()
  return { frame_count = frame_count, columns = columns, rows = rows }
end

operations.inspect_cels = function(input)
  local sprite = open_sprite(input.source_path)
  local groups, next_group, cels = {}, 1, {}
  for _, cel in ipairs(sprite.cels) do
    local image_id = cel.image.id
    if groups[image_id] == nil then groups[image_id], next_group = next_group, next_group + 1 end
    local layer_path = cel.layer.name
    local parent = cel.layer.parent
    while parent ~= nil and parent.name ~= nil do
      layer_path = parent.name .. "/" .. layer_path
      parent = parent.parent
    end
    table.insert(cels, { layer = layer_path, frame = cel.frame.frameNumber - 1,
      position = point_info(cel.position), bounds = rectangle_info(cel.bounds),
      opacity = cel.opacity, z_index = cel.zIndex, image_id = image_id,
      linked_group = groups[image_id] })
  end
  sprite:close()
  return { cels = cels }
end

operations.analyze_palette = function(input)
  local sprite = open_sprite(input.source_path)
  local counts, frame_sets, transparent, visits = {}, {}, 0, 0
  for _, cel in ipairs(sprite.cels) do
    if not cel.layer.isTilemap then
      for pixel in cel.image:pixels() do
        visits = visits + 1
        if visits > input.max_pixel_visits then fail("LIMIT_EXCEEDED", "palette analysis exceeds pixel limit") end
        local red, green, blue, alpha = pixel_rgba(sprite, cel.layer, pixel())
        if alpha == 0 then transparent = transparent + 1 else
          local key = rgba_hex(red, green, blue, alpha)
          counts[key] = (counts[key] or 0) + 1
          frame_sets[key] = frame_sets[key] or {}
          frame_sets[key][cel.frame.frameNumber] = true
        end
      end
    end
  end
  local usages, keys = {}, {}
  for color, pixels in pairs(counts) do
    local frames = 0
    for _ in pairs(frame_sets[color]) do frames = frames + 1 end
    table.insert(usages, { color = color, pixels = pixels, frames = frames })
    table.insert(keys, color)
  end
  table.sort(usages, function(a, b) return a.pixels > b.pixels end)
  local unused = {}
  local palette = sprite.palettes[1]
  if palette ~= nil then
    for index = 0, #palette - 1 do
      local color = color_info(palette:getColor(index)).hex
      if counts[color] == nil then table.insert(unused, color) end
    end
  end
  local near = {}
  local used = {}
  for i = 1, #keys do
    if not used[i] then
      local group = { keys[i] }
      local a = parse_color(keys[i])
      for j = i + 1, #keys do
        local b = parse_color(keys[j])
        local distance = math.abs(a.red-b.red)+math.abs(a.green-b.green)+math.abs(a.blue-b.blue)
        if distance <= input.near_duplicate_distance then table.insert(group, keys[j]); used[j] = true end
      end
      if #group > 1 then table.insert(near, group) end
    end
  end
  sprite:close()
  return { unique_colors = #keys, transparent_pixels = transparent, usages = usages,
    unused_palette_colors = unused, near_duplicate_groups = near }
end

local function selected_layer(input, sprite, layer)
  if #(input.layers or {}) == 0 then return true end
  for _, path in ipairs(input.layers) do if find_layer(sprite, path) == layer then return true end end
  return false
end

local function selected_frame(input, frame_number)
  if #(input.frames or {}) == 0 then return true end
  for _, frame in ipairs(input.frames) do if frame + 1 == frame_number then return true end end
  return false
end

operations.replace_color = function(input)
  local sprite = open_sprite(input.source_path)
  local from, to = parse_color(input.from_color), parse_color(input.to_color)
  app.transaction("MCP replace color", function()
    for _, cel in ipairs(sprite.cels) do
      if not cel.layer.isTilemap and selected_layer(input, sprite, cel.layer) and selected_frame(input, cel.frame.frameNumber) then
        local image = Image(cel.image)
        for pixel in image:pixels() do
          local r,g,b,a = pixel_rgba(sprite, cel.layer, pixel())
          local distance = math.abs(r-from.red)+math.abs(g-from.green)+math.abs(b-from.blue)+math.abs(a-from.alpha)
          if distance <= input.tolerance then pixel(to) end
        end
        cel.image = image
      end
    end
  end)
  save_copy(sprite, input.output_path); local result=inspect_sprite(sprite,false,input.output_path); sprite:close(); return result
end

operations.fill_region = function(input)
  local sprite = open_sprite(input.source_path); local layer=find_layer(sprite,input.layer)
  if layer.isGroup or layer.isTilemap then fail("INVALID_SELECTOR", "fill requires image layer") end
  local frame=input.frame+1; if frame < 1 or frame > #sprite.frames then fail("INVALID_SELECTOR", "frame outside sprite") end
  if input.x >= sprite.width or input.y >= sprite.height then fail("INVALID_SELECTOR", "fill point outside sprite") end
  app.transaction("MCP fill region", function()
    local cel=layer:cel(frame); local image=Image(sprite.spec)
    if cel ~= nil then image:drawImage(cel.image,cel.position) end
    local target=image:getPixel(input.x,input.y); local replacement=parse_color(input.color)
    local queue={{input.x,input.y}}; local head=1; local seen={}
    local visits=0
    while head <= #queue do local point=queue[head]; head=head+1; local x,y=point[1],point[2]; local key=y*sprite.width+x
      if x>=0 and x<sprite.width and y>=0 and y<sprite.height and not seen[key] then seen[key]=true
        visits=visits+1;if visits>input.max_pixel_visits then fail("LIMIT_EXCEEDED","fill exceeds pixel limit") end
        if image:getPixel(x,y)==target then image:drawPixel(x,y,replacement)
          if input.contiguous then table.insert(queue,{x-1,y});table.insert(queue,{x+1,y});table.insert(queue,{x,y-1});table.insert(queue,{x,y+1}) end
        end
      end
    end
    if not input.contiguous then for y=0,sprite.height-1 do for x=0,sprite.width-1 do if image:getPixel(x,y)==target then image:drawPixel(x,y,replacement) end end end end
    if cel then cel.image=image;cel.position=Point(0,0) else sprite:newCel(layer,frame,image,Point(0,0)) end
  end)
  save_copy(sprite,input.output_path);local result=inspect_sprite(sprite,false,input.output_path);sprite:close();return result
end

operations.draw_shapes = function(input)
  local sprite=open_sprite(input.source_path);local layer=find_layer(sprite,input.layer);local frame=input.frame+1
  if layer.isGroup or layer.isTilemap or frame>#sprite.frames then fail("INVALID_SELECTOR","invalid shape target") end
  app.transaction("MCP draw shapes",function() for _,shape in ipairs(input.shapes) do
    if math.min(shape.x1,shape.x2,shape.y1,shape.y2)<0 or math.max(shape.x1,shape.x2)>=sprite.width or math.max(shape.y1,shape.y2)>=sprite.height then fail("INVALID_SELECTOR","shape outside sprite") end
    app.useTool{tool=shape.shape,color=parse_color(shape.color),brush=Brush(1),layer=layer,
      frame=sprite.frames[frame],points={Point(shape.x1,shape.y1),Point(shape.x2,shape.y2)}} end end)
  save_copy(sprite,input.output_path);local result=inspect_sprite(sprite,false,input.output_path);sprite:close();return result
end

operations.edit_selection = function(input)
  local sprite=open_sprite(input.source_path)
  app.transaction("MCP edit selection",function() for _,op in ipairs(input.operations) do
    if op.action=="clear" then sprite.selection:deselect() elseif op.action=="all" then sprite.selection:selectAll() else
      if op.bounds==nil then fail("INVALID_INPUT","selection bounds required") end
      local rect=Rectangle(op.bounds.x,op.bounds.y,op.bounds.width,op.bounds.height)
      if op.action=="replace" then sprite.selection:select(rect) elseif op.action=="add" then sprite.selection:add(rect)
      elseif op.action=="subtract" then sprite.selection:subtract(rect) elseif op.action=="intersect" then sprite.selection:intersect(rect) end
    end end end)
  save_copy(sprite,input.output_path);local result=inspect_sprite(sprite,false,input.output_path);sprite:close();return result
end

operations.apply_outline = function(input)
  local sprite=open_sprite(input.source_path);local layer=find_layer(sprite,input.layer);local frame=input.frame+1
  if layer.isGroup or layer.isTilemap then fail("INVALID_SELECTOR","outline requires a writable image layer") end
  if frame<1 or frame>#sprite.frames then fail("INVALID_SELECTOR","frame index is outside the sprite") end
  app.layer=layer;app.frame=sprite.frames[frame]
  app.transaction("MCP outline",function() app.command.Outline{ui=false,color=parse_color(input.color),place=input.place,matrix=input.matrix} end)
  save_copy(sprite,input.output_path);local result=inspect_sprite(sprite,false,input.output_path);sprite:close();return result
end

operations.inspect_tilesets = function(input)
  local sprite=open_sprite(input.source_path);local tilesets,layers={},{}
  for _,ts in ipairs(sprite.tilesets) do local size=ts.grid.tileSize;table.insert(tilesets,{name=ts.name,tile_width=size.width,tile_height=size.height,tile_count=#ts,base_index=ts.baseIndex}) end
  local function walk(items,prefix) for _,layer in ipairs(items) do local path=prefix=="" and layer.name or prefix.."/"..layer.name;if layer.isTilemap then table.insert(layers,path) end;if layer.isGroup then walk(layer.layers,path) end end end
  walk(sprite.layers,"");sprite:close();return {tilesets=tilesets,tilemap_layers=layers}
end

operations.edit_tilemap = function(input)
  local sprite=open_sprite(input.source_path);local ts=find_tileset(sprite,input.tileset);local layer
  if input.create_layer then app.command.NewLayer{name=input.layer,tilemap=true};layer=app.layer;layer.tileset=ts else layer=find_layer(sprite,input.layer) end
  if not layer.isTilemap then fail("INVALID_SELECTOR","target is not tilemap layer") end
  local frame=input.frame+1;if frame>#sprite.frames then fail("INVALID_SELECTOR","frame outside sprite") end
  app.transaction("MCP edit tilemap",function() local cel=layer:cel(frame);if cel==nil then cel=sprite:newCel(layer,frame) end;local image=Image(cel.image)
    for _,cell in ipairs(input.cells) do if cell.x>=image.width or cell.y>=image.height then fail("INVALID_SELECTOR","tilemap cell outside map") end
      local flags=0;if cell.flip_x then flags=flags+0x20000000 end;if cell.flip_y then flags=flags+0x40000000 end;if cell.flip_diagonal then flags=flags+0x80000000 end
      image:drawPixel(cell.x,cell.y,app.pixelColor.tile(cell.tile_index,flags)) end;cel.image=image end)
  save_copy(sprite,input.output_path);local result=inspect_sprite(sprite,false,input.output_path);sprite:close();return result
end

operations.validate_tileset = function(input)
  local sprite=open_sprite(input.source_path);local ts=find_tileset(sprite,input.tileset);local empty,signatures,duplicates,issues={}, {}, {}, {};local visits=0
  for index=1,#ts-1 do local image=ts:tile(index).image;local signature="";local opaque=0
    for pixel in image:pixels() do visits=visits+1;if visits>input.max_pixel_visits then fail("LIMIT_EXCEEDED","tileset validation exceeds pixel limit") end;local value=pixel();signature=signature..tostring(value)..",";if pixel_alpha(sprite,{isBackground=false},value)>0 then opaque=opaque+1 end end
    if opaque==0 then table.insert(empty,index) end;signatures[signature]=signatures[signature] or {};table.insert(signatures[signature],index)
    if input.check_edges then for y=0,image.height-1 do if image:getPixel(0,y)~=image:getPixel(image.width-1,y) then table.insert(issues,{code="EDGE_X_MISMATCH",severity="warning",message="Opposite horizontal edges differ",tile_indices={index}});break end end end
  end
  for _,group in pairs(signatures) do if #group>1 then table.insert(duplicates,group) end end
  if #empty>0 then table.insert(issues,{code="EMPTY_TILES",severity="warning",message="Tileset contains empty tiles",tile_indices=empty}) end
  for _,group in ipairs(duplicates) do table.insert(issues,{code="DUPLICATE_TILES",severity="warning",message="Tileset contains pixel-identical tiles",tile_indices=group}) end
  sprite:close();return {tileset=input.tileset,valid=true,issues=issues,empty_tiles=empty,duplicate_groups=duplicates}
end

operations.export_tileset = function(input)
  local sprite=open_sprite(input.source_path);local ts=find_tileset(sprite,input.tileset);local size=ts.grid.tileSize;local count=#ts-1;local columns=math.min(input.columns,math.max(count,1));local rows=math.ceil(math.max(count,1)/columns)
  if columns*size.width*rows*size.height>input.max_pixels then fail("LIMIT_EXCEEDED","tileset export exceeds pixel limit") end
  local sheet=Image(columns*size.width,rows*size.height,sprite.colorMode);sheet:clear();local entries={}
  for index=1,count do local x=((index-1)%columns)*size.width;local y=math.floor((index-1)/columns)*size.height;sheet:drawImage(ts:tile(index).image,Point(x,y));table.insert(entries,{index=index,x=x,y=y,width=size.width,height=size.height}) end
  if sprite.colorMode==ColorMode.INDEXED then sheet:saveAs{filename=input.image_output_path,palette=sprite.palettes[1]} else sheet:saveAs(input.image_output_path) end
  write_all(input.data_output_path,json.encode({tileset=input.tileset,tile_width=size.width,tile_height=size.height,tiles=entries}));sprite:close();return {tile_count=count}
end

operations.crop_sprite = function(input)
  local sprite = open_sprite(input.source_path)
  for _, frame in ipairs(input.frames or {}) do
    if frame < 0 or frame >= #sprite.frames then fail("INVALID_SELECTOR", "crop frame is outside the sprite") end
  end
  local function effectively_visible(layer)
    local current = layer
    while current ~= nil do
      if not current.isVisible then return false end
      current = current.parent
    end
    return true
  end
  local left, top, right, bottom, visits = nil, nil, nil, nil, 0
  for _, cel in ipairs(sprite.cels) do
    if not cel.layer.isTilemap and effectively_visible(cel.layer) and
       selected_layer(input, sprite, cel.layer) and
       selected_frame(input, cel.frame.frameNumber) then
      for pixel in cel.image:pixels() do
        visits = visits + 1
        if visits > input.max_pixel_visits then
          fail("LIMIT_EXCEEDED", "crop analysis exceeds pixel visit limit")
        end
        if pixel_alpha(sprite, cel.layer, pixel()) > 0 then
          local x, y = cel.position.x + pixel.x, cel.position.y + pixel.y
          if x >= 0 and x < sprite.width and y >= 0 and y < sprite.height then
            left = left == nil and x or math.min(left, x)
            top = top == nil and y or math.min(top, y)
            right = right == nil and x or math.max(right, x)
            bottom = bottom == nil and y or math.max(bottom, y)
          end
        end
      end
    end
  end
  if left == nil then fail("EMPTY_SELECTION", "selected frames and layers contain no visible pixels") end
  left = math.max(0, left - input.padding)
  top = math.max(0, top - input.padding)
  right = math.min(sprite.width - 1, right + input.padding)
  bottom = math.min(sprite.height - 1, bottom + input.padding)
  app.transaction("MCP crop sprite", function()
    sprite:crop(Rectangle(left, top, right - left + 1, bottom - top + 1))
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.draw_strokes = function(input)
  local sprite = open_sprite(input.source_path)
  local layer = find_layer(sprite, input.layer)
  local frame = input.frame + 1
  if layer.isGroup or layer.isTilemap then fail("INVALID_SELECTOR", "strokes require an image layer") end
  if frame < 1 or frame > #sprite.frames then fail("INVALID_SELECTOR", "frame index is outside the sprite") end
  app.transaction("MCP draw strokes", function()
    for _, stroke in ipairs(input.strokes) do
      local points = {}
      for _, point in ipairs(stroke.points) do
        if point.x < 0 or point.x >= sprite.width or point.y < 0 or point.y >= sprite.height then
          fail("INVALID_SELECTOR", "stroke point is outside the sprite")
        end
        table.insert(points, Point(point.x, point.y))
      end
      app.useTool {
        tool = "pencil",
        color = parse_color(stroke.color),
        brush = Brush(stroke.brush_size),
        layer = layer,
        frame = sprite.frames[frame],
        points = points,
        opacity = stroke.opacity,
        freehandAlgorithm = stroke.pixel_perfect and 1 or 0
      }
    end
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.transform_selection = function(input)
  local sprite = open_sprite(input.source_path)
  local layer = find_layer(sprite, input.layer)
  local frame = input.frame + 1
  local bounds = input.bounds
  if layer.isGroup or layer.isTilemap or layer.isBackground then
    fail("INVALID_SELECTOR", "selection transforms require a non-background image layer")
  end
  if frame < 1 or frame > #sprite.frames then fail("INVALID_SELECTOR", "frame index is outside the sprite") end
  if bounds.x < 0 or bounds.y < 0 or bounds.x + bounds.width > sprite.width or
     bounds.y + bounds.height > sprite.height then
    fail("INVALID_SELECTOR", "selection bounds extend outside the sprite")
  end
  local cel = layer:cel(frame)
  local canvas = Image(sprite.spec)
  canvas:clear()
  if cel ~= nil then canvas:drawImage(cel.image, cel.position) end
  local region = Image(canvas, Rectangle(bounds.x, bounds.y, bounds.width, bounds.height))
  local transformed = region
  if input.action == "flip_horizontal" or input.action == "flip_vertical" or
     input.action == "rotate_90_cw" or input.action == "rotate_90_ccw" then
    transformed = transformed_image(sprite, region, input.action)
  elseif input.action == "scale_nearest" then
    transformed = Image(region)
    transformed:resize(bounds.width * input.scale_x, bounds.height * input.scale_y)
  end
  local target_x = bounds.x + input.offset_x
  local target_y = bounds.y + input.offset_y
  if target_x < 0 or target_y < 0 or target_x + transformed.width > sprite.width or
     target_y + transformed.height > sprite.height then
    fail("INVALID_SELECTOR", "transformed selection extends outside the sprite")
  end
  if bounds.width * bounds.height + transformed.width * transformed.height > input.max_pixel_visits then
    fail("LIMIT_EXCEEDED", "selection transform exceeds pixel visit limit")
  end
  app.transaction("MCP transform selection", function()
    if input.action ~= "copy" then
      canvas:clear(Rectangle(bounds.x, bounds.y, bounds.width, bounds.height))
    end
    canvas:drawImage(transformed, Point(target_x, target_y))
    if cel == nil then cel = sprite:newCel(layer, frame, canvas, Point(0, 0))
    else cel.image = canvas; cel.position = Point(0, 0) end
    sprite.selection:select(Rectangle(target_x, target_y, transformed.width, transformed.height))
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

local function remap_indexed_pixels(sprite, mapper, max_pixel_visits, visits)
  if sprite.colorMode ~= ColorMode.INDEXED then return visits end
  local seen = {}
  local function remap_image(image)
    if seen[image.id] then return end
    seen[image.id] = true
    for pixel in image:pixels() do
      visits = visits + 1
      if visits > max_pixel_visits then fail("LIMIT_EXCEEDED", "palette remap exceeds pixel visit limit") end
      local mapped = mapper(pixel())
      if mapped ~= pixel() then pixel(mapped) end
    end
  end
  for _, cel in ipairs(sprite.cels) do
    if not cel.layer.isTilemap and not seen[cel.image.id] then
      remap_image(cel.image)
    end
  end
  for _, tileset in ipairs(sprite.tilesets) do
    for index = 1, #tileset - 1 do remap_image(tileset:tile(index).image) end
  end
  return visits
end

operations.edit_palette_entries = function(input)
  local sprite = open_sprite(input.source_path)
  if #sprite.palettes ~= 1 then
    fail("UNSUPPORTED_DOCUMENT", "palette entry editing requires exactly one sprite palette")
  end
  local palette = sprite.palettes[1]
  if palette == nil then fail("INVALID_SPRITE", "sprite does not contain a palette") end
  local pixel_visits = 0
  app.transaction("MCP edit palette entries", function()
    for _, operation in ipairs(input.operations) do
      local size = #palette
      if operation.action == "set" then
        if operation.index >= size then fail("INVALID_SELECTOR", "palette index is outside the palette") end
        palette:setColor(operation.index, parse_color(operation.color))
      elseif operation.action == "append" then
        if size >= 256 then fail("LIMIT_EXCEEDED", "palette cannot exceed 256 entries") end
        palette:resize(size + 1)
        palette:setColor(size, parse_color(operation.color))
      elseif operation.action == "remove" then
        local removed, replacement = operation.index, operation.replacement_index
        if size <= 1 or removed >= size or replacement >= size or removed == replacement then
          fail("INVALID_SELECTOR", "invalid palette removal or replacement index")
        end
        local replacement_after = replacement > removed and replacement - 1 or replacement
        pixel_visits = remap_indexed_pixels(sprite, function(value)
          if value == removed then return replacement_after end
          if value > removed then return value - 1 end
          return value
        end, input.max_pixel_visits, pixel_visits)
        for index = removed, size - 2 do palette:setColor(index, palette:getColor(index + 1)) end
        palette:resize(size - 1)
        if sprite.transparentColor == removed then sprite.transparentColor = replacement_after
        elseif sprite.transparentColor > removed then sprite.transparentColor = sprite.transparentColor - 1 end
      elseif operation.action == "swap" then
        local first, second = operation.index, operation.other_index
        if first >= size or second >= size then fail("INVALID_SELECTOR", "palette index is outside the palette") end
        local first_color, second_color = palette:getColor(first), palette:getColor(second)
        palette:setColor(first, second_color); palette:setColor(second, first_color)
        if operation.preserve_appearance then
          pixel_visits = remap_indexed_pixels(sprite, function(value)
            if value == first then return second end
            if value == second then return first end
            return value
          end, input.max_pixel_visits, pixel_visits)
          if sprite.transparentColor == first then sprite.transparentColor = second
          elseif sprite.transparentColor == second then sprite.transparentColor = first end
        end
      end
    end
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

local function layer_signature(sprite)
  local values = {}
  local function walk(layers, prefix)
    for _, layer in ipairs(layers) do
      local path = prefix == "" and layer.name or prefix .. "/" .. layer.name
      local kind = layer.isGroup and "group" or (layer.isTilemap and "tilemap" or
        (layer.isBackground and "background" or "image"))
      table.insert(values, path .. ":" .. kind)
      if layer.isGroup then walk(layer.layers, path) end
    end
  end
  walk(sprite.layers, "")
  return table.concat(values, "|")
end

local function tag_signature(sprite)
  local values = {}
  for _, tag in ipairs(sprite.tags) do
    table.insert(values, tag.name .. ":" .. tag.fromFrame.frameNumber .. ":" ..
      tag.toFrame.frameNumber .. ":" .. animation_direction_name(tag.aniDir) .. ":" ..
      tostring(tag.repeats or 0))
  end
  return table.concat(values, "|")
end

local function palette_signature(sprite)
  local values = {}
  for _, palette in ipairs(sprite.palettes) do
    local frame = 1
    if type(palette.frame) == "number" then frame = palette.frame
    elseif palette.frame ~= nil then frame = palette.frame.frameNumber end
    table.insert(values, "frame=" .. frame .. ":size=" .. #palette)
    for index = 0, #palette - 1 do
      local color = palette:getColor(index)
      table.insert(values, rgba_hex(color.red, color.green, color.blue, color.alpha))
    end
  end
  return table.concat(values, "|")
end

local function slice_signature(sprite)
  local values = {}
  for _, slice in ipairs(sprite.slices) do
    local bounds = slice.bounds
    local value = slice.name .. ":" .. bounds.x .. ":" .. bounds.y .. ":" ..
      bounds.width .. ":" .. bounds.height
    if slice.center ~= nil then
      local center = slice.center
      value = value .. ":c=" .. center.x .. "," .. center.y .. "," ..
        center.width .. "," .. center.height
    end
    if slice.pivot ~= nil then
      value = value .. ":p=" .. slice.pivot.x .. "," .. slice.pivot.y
    end
    table.insert(values, value)
  end
  return table.concat(values, "|")
end

operations.compare_sprites = function(input)
  local first = open_sprite(input.first_source_path)
  local second = open_sprite(input.second_source_path)
  local same_dimensions = first.width == second.width and first.height == second.height
  local same_frame_count = #first.frames == #second.frames
  local same_color_mode = first.colorMode == second.colorMode
  local changed_frames, total_changed, visits = {}, 0, 0
  local width, height = math.max(first.width, second.width), math.max(first.height, second.height)
  local frame_count = math.max(#first.frames, #second.frames)
  for frame = 1, frame_count do
    local first_image = frame <= #first.frames and render_frame_image(first, frame) or nil
    local second_image = frame <= #second.frames and render_frame_image(second, frame) or nil
    local changed, left, top, right, bottom = 0, nil, nil, nil, nil
    for y = 0, height - 1 do for x = 0, width - 1 do
      visits = visits + 1
      if visits > input.max_pixel_visits then fail("LIMIT_EXCEEDED", "sprite comparison exceeds pixel visit limit") end
      local ar, ag, ab, aa = 0, 0, 0, 0
      local br, bg, bb, ba = 0, 0, 0, 0
      if first_image ~= nil and x < first.width and y < first.height then
        ar, ag, ab, aa = pixel_rgba(first, nil, first_image:getPixel(x, y))
      end
      if second_image ~= nil and x < second.width and y < second.height then
        br, bg, bb, ba = pixel_rgba(second, nil, second_image:getPixel(x, y))
      end
      if ar ~= br or ag ~= bg or ab ~= bb or aa ~= ba then
        changed = changed + 1
        left = left == nil and x or math.min(left, x); top = top == nil and y or math.min(top, y)
        right = right == nil and x or math.max(right, x); bottom = bottom == nil and y or math.max(bottom, y)
      end
    end end
    if changed > 0 then
      table.insert(changed_frames, {frame=frame-1, changed_pixel_count=changed,
        changed_bounds={x=left,y=top,width=right-left+1,height=bottom-top+1}})
      total_changed = total_changed + changed
    end
  end
  local same_layers = layer_signature(first) == layer_signature(second)
  local same_tags = tag_signature(first) == tag_signature(second)
  local same_slices = slice_signature(first) == slice_signature(second)
  local same_palette = palette_signature(first) == palette_signature(second)
  first:close(); second:close()
  return {identical=same_dimensions and same_frame_count and same_color_mode and same_layers and
      same_palette and same_tags and same_slices and total_changed==0,
    same_dimensions=same_dimensions, same_frame_count=same_frame_count,
    same_color_mode=same_color_mode, same_palette=same_palette, same_layer_structure=same_layers,
    same_tags=same_tags, same_slices=same_slices,
    changed_pixel_count=total_changed, changed_frames=changed_frames}
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
