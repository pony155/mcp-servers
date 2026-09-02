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

operations.quantize_palette = function(input)
  local sprite = open_sprite(input.source_path)
  app.sprite = sprite
  app.transaction("MCP quantize palette", function()
    app.command.ColorQuantization {
      ui = false,
      withAlpha = input.include_alpha,
      maxColors = input.color_count,
      useRange = false,
      algorithm = input.algorithm
    }
    local options = {format="indexed", rgbmap=input.algorithm}
    if input.dithering ~= "none" then
      options.dithering = input.dithering
      options["dithering-matrix"] = input.dithering_matrix
    end
    app.command.ChangePixelFormat(options)
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.import_palette = function(input)
  local sprite = open_sprite(input.source_path)
  local palette = Palette {fromFile=input.palette_path}
  if palette == nil or #palette < 1 or #palette > 256 then
    fail("INVALID_PALETTE", "palette file could not be loaded or exceeds 256 colors")
  end
  app.transaction("MCP import palette", function() sprite:setPalette(palette) end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.export_palette = function(input)
  local sprite = open_sprite(input.source_path)
  local palette = sprite.palettes[1]
  if palette == nil then fail("INVALID_SPRITE", "sprite does not contain a palette") end
  local saved = palette:saveAs(input.output_path)
  if saved == false then fail("ASEPRITE_FAILED", "Aseprite could not export the palette") end
  sprite:close()
  return {color_count=#palette}
end

operations.palette_cycle = function(input)
  local sprite = open_sprite(input.source_path)
  if sprite.colorMode ~= ColorMode.INDEXED then
    fail("INVALID_SPRITE", "palette cycling requires an indexed-color sprite")
  end
  if input.first_frame < 0 or input.last_frame >= #sprite.frames then
    fail("INVALID_SELECTOR", "palette-cycle frame range is outside the sprite")
  end
  local palette = sprite.palettes[1]
  local positions = {}
  for position, index in ipairs(input.indices) do
    if index >= #palette then fail("INVALID_SELECTOR", "palette index is outside the palette") end
    positions[index] = position
  end
  local visits = 0
  app.transaction("MCP palette cycle", function()
    for zero_frame = input.first_frame, input.last_frame do
      local shift = input.step * (zero_frame - input.first_frame)
      for _, cel in ipairs(sprite.cels) do
        if cel.frame.frameNumber == zero_frame + 1 and not cel.layer.isTilemap then
          local image = Image(cel.image)
          for pixel in image:pixels() do
            visits = visits + 1
            if visits > input.max_pixel_visits then
              fail("LIMIT_EXCEEDED", "palette cycle exceeds the pixel visit limit")
            end
            local position = positions[pixel()]
            if position ~= nil then
              local target = ((position - 1 + shift) % #input.indices) + 1
              pixel(input.indices[target])
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
