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

operations.merge_layers = function(input)
  local sprite = open_sprite(input.source_path)
  app.sprite = sprite
  app.transaction("MCP merge layers", function()
    if input.mode == "flatten" then
      app.command.FlattenLayers {visibleOnly=input.visible_only}
    else
      local layer = find_layer(sprite, input.layer)
      if layer.stackIndex <= 1 then fail("INVALID_SELECTOR", "layer has nothing below to merge") end
      app.layer = layer
      local merged = app.command.MergeDownLayer()
      if merged == false then fail("ASEPRITE_FAILED", "Aseprite could not merge the layer down") end
    end
    if input.output_layer_name ~= nil then app.layer.name = input.output_layer_name end
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.import_frames = function(input)
  local sprite = open_sprite(input.source_path)
  local layer = find_layer(sprite, input.layer)
  if layer.isGroup or layer.isTilemap or layer.isBackground then
    fail("INVALID_SELECTOR", "frame import requires a non-background image layer")
  end
  if #sprite.frames + #input.frame_paths > 256 then fail("LIMIT_EXCEEDED", "frame count exceeds 256") end
  if input.insert_at ~= nil and input.insert_at > #sprite.frames then
    fail("INVALID_SELECTOR", "frame insertion index is outside the sprite")
  end
  app.transaction("MCP import frames", function()
    for offset, path in ipairs(input.frame_paths) do
      local imported = Image {fromFile=path}
      if imported == nil then fail("INVALID_IMAGE", "Aseprite could not load an imported frame") end
      if imported.width ~= sprite.width or imported.height ~= sprite.height then
        fail("INVALID_INPUT", "imported frame dimensions must match the sprite canvas")
      end
      local frame
      if input.insert_at == nil then frame = sprite:newEmptyFrame()
      else frame = sprite:newEmptyFrame(input.insert_at + offset) end
      frame.duration = input.duration_ms / 1000
      local image = Image(sprite.spec); image:clear(); image:drawImage(imported, Point(0, 0))
      sprite:newCel(layer, frame, image, Point(0, 0))
    end
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.edit_grid = function(input)
  local sprite = open_sprite(input.source_path)
  app.transaction("MCP edit grid", function()
    sprite.gridBounds = Rectangle(input.x, input.y, input.width, input.height)
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

local function blend_mode_value(name)
  local values={normal=BlendMode.NORMAL,multiply=BlendMode.MULTIPLY,screen=BlendMode.SCREEN,
    overlay=BlendMode.OVERLAY,darken=BlendMode.DARKEN,lighten=BlendMode.LIGHTEN,
    color_dodge=BlendMode.COLOR_DODGE,color_burn=BlendMode.COLOR_BURN,
    hard_light=BlendMode.HARD_LIGHT,soft_light=BlendMode.SOFT_LIGHT,
    difference=BlendMode.DIFFERENCE,exclusion=BlendMode.EXCLUSION,hsl_hue=BlendMode.HSL_HUE,
    hsl_saturation=BlendMode.HSL_SATURATION,hsl_color=BlendMode.HSL_COLOR,
    hsl_luminosity=BlendMode.HSL_LUMINOSITY,addition=BlendMode.ADDITION,
    subtract=BlendMode.SUBTRACT,divide=BlendMode.DIVIDE}
  return values[name]
end

operations.edit_blend_modes = function(input)
  local sprite = open_sprite(input.source_path)
  app.transaction("MCP edit blend modes", function()
    for _, operation in ipairs(input.operations) do
      local layer=find_layer(sprite,operation.layer)
      if layer.isGroup then fail("INVALID_SELECTOR", "group layers do not expose a blend mode") end
      local value=blend_mode_value(operation.blend_mode)
      if value==nil then fail("INVALID_INPUT", "unsupported blend mode") end
      layer.blendMode=value
    end
  end)
  save_copy(sprite,input.output_path)
  local result=inspect_sprite(sprite,false,input.output_path);sprite:close();return result
end

operations.edit_cels = function(input)
  local sprite = open_sprite(input.source_path)
  app.transaction("MCP edit cels", function()
    for _, operation in ipairs(input.operations) do
      local layer = find_layer(sprite, operation.layer)
      if layer.isGroup then fail("INVALID_SELECTOR", "group layers do not contain cels") end
      local frame = operation.frame + 1
      if frame < 1 or frame > #sprite.frames then
        fail("INVALID_SELECTOR", "cel frame is outside the sprite")
      end
      local cel = layer:cel(frame)
      if cel == nil then fail("INVALID_SELECTOR", "cel was not found") end
      if operation.action == "set_position" then
        cel.position = Point(operation.x, operation.y)
      elseif operation.action == "set_opacity" then
        cel.opacity = operation.opacity
      elseif operation.action == "set_z_index" then
        cel.zIndex = operation.z_index
      elseif operation.action == "unlink" then
        cel.image = Image(cel.image)
      elseif operation.action == "remove" then
        sprite:deleteCel(cel)
      else
        fail("INVALID_INPUT", "unsupported cel edit action")
      end
    end
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.edit_color_space = function(input)
  local sprite = open_sprite(input.source_path)
  local color_space
  if input.mode == "assign_none" then color_space = ColorSpace()
  elseif input.mode == "assign_srgb" or input.mode == "convert_srgb" then
    color_space = ColorSpace {sRGB=true}
  elseif input.mode == "assign_icc" or input.mode == "convert_icc" then
    color_space = ColorSpace {fromFile=input.profile_path}
  else fail("INVALID_INPUT", "unsupported color-space mode") end
  if color_space == nil then fail("INVALID_INPUT", "color profile could not be loaded") end
  app.transaction("MCP edit color space", function()
    if input.mode == "convert_srgb" or input.mode == "convert_icc" then
      sprite:convertColorSpace(color_space)
    else sprite:assignColorSpace(color_space) end
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

local function inspected_scalar_properties(properties)
  local result = {}
  for key, value in pairs(properties) do
    local kind = type(value)
    if type(key) == "string" and
      (kind == "string" or kind == "number" or kind == "boolean") then
      result[key] = value
    end
  end
  return result
end

operations.inspect_properties = function(input)
  local sprite = open_sprite(input.source_path)
  local selected = {}
  for _, target in ipairs(input.targets or {}) do selected[target] = true end
  local all = next(selected) == nil
  local items = {}
  local function add(target, identifier, object, frame)
    local properties = inspected_scalar_properties(object.properties)
    local data = object.data or ""
    local color = object.color or Color { r=0, g=0, b=0, a=0 }
    if input.include_empty or data ~= "" or next(properties) ~= nil or color.alpha > 0 then
      if #items >= input.max_items then fail("LIMIT_EXCEEDED", "property inspection exceeds item limit") end
      table.insert(items, {target=target, identifier=identifier, frame=frame,
        data=data, color=rgba_hex(color.red, color.green, color.blue, color.alpha),
        properties=properties})
    end
  end
  if all or selected.sprite then add("sprite", "sprite", sprite, nil) end
  local function walk(layers, prefix)
    for _, layer in ipairs(layers) do
      local path = prefix == "" and layer.name or prefix .. "/" .. layer.name
      if all or selected.layer then add("layer", path, layer, nil) end
      if all or selected.cel then
        for _, cel in ipairs(layer.cels or {}) do
          add("cel", path, cel, cel.frame.frameNumber - 1)
        end
      end
      if layer.isGroup then walk(layer.layers, path) end
    end
  end
  walk(sprite.layers, "")
  if all or selected.tag then
    for _, tag in ipairs(sprite.tags) do add("tag", tag.name, tag, nil) end
  end
  if all or selected.slice then
    for _, slice in ipairs(sprite.slices) do add("slice", slice.name, slice, nil) end
  end
  for _, tileset in ipairs(sprite.tilesets) do
    if all or selected.tileset then add("tileset", tileset.name, tileset, nil) end
    if all or selected.tile then
      for index = 0, #tileset - 1 do
        add("tile", tileset.name .. "#" .. tostring(index), tileset:tile(index), nil)
      end
    end
  end
  sprite:close()
  return {items=items}
end

operations.copy_layer_tree = function(input)
  local sprite = open_sprite(input.source_path)
  local donor = open_sprite(input.donor_path)
  if sprite.width ~= donor.width or sprite.height ~= donor.height or
    sprite.colorMode ~= donor.colorMode then
    donor:close(); sprite:close()
    fail("INVALID_INPUT", "source and donor canvas dimensions and color mode must match")
  end
  local source_layer = find_layer(donor, input.layer)
  local target_parent = nil
  if input.target_parent ~= nil then
    target_parent = find_layer(sprite, input.target_parent)
    if not target_parent.isGroup then
      donor:close(); sprite:close(); fail("INVALID_SELECTOR", "target_parent must be a group")
    end
  end
  local layer_count = 0
  local function verify(layer)
    layer_count = layer_count + 1
    if layer_count > input.max_layers then fail("LIMIT_EXCEEDED", "layer tree exceeds limit") end
    if layer.isTilemap or layer.isBackground then
      fail("INVALID_INPUT", "copy_layer_tree supports transparent image layers and groups only")
    end
    if layer.isGroup then for _, child in ipairs(layer.layers) do verify(child) end end
  end
  verify(source_layer)
  if #donor.frames > input.max_frames then
    donor:close(); sprite:close(); fail("LIMIT_EXCEEDED", "donor frame count exceeds limit")
  end
  while #sprite.frames < #donor.frames do
    local frame = sprite:newEmptyFrame()
    frame.duration = donor.frames[frame.frameNumber].duration
  end
  local visits = 0
  local function copy_fields(source, target)
    target.data = source.data
    target.color = source.color
    for key, value in pairs(source.properties) do target.properties[key] = value end
  end
  local function clone(source, parent, top)
    local target = source.isGroup and sprite:newGroup() or sprite:newLayer()
    target.name = top and (input.new_name or source.name) or source.name
    if parent ~= nil then target.parent = parent end
    target.isVisible = source.isVisible
    target.opacity = source.opacity
    copy_fields(source, target)
    if source.isGroup then
      for _, child in ipairs(source.layers) do clone(child, target, false) end
    else
      target.blendMode = source.blendMode
      for _, cel in ipairs(source.cels) do
        visits = visits + cel.image.width * cel.image.height
        if visits > input.max_pixel_visits then fail("LIMIT_EXCEEDED", "layer copy exceeds pixel limit") end
        local copied = sprite:newCel(target, cel.frame.frameNumber, Image(cel.image), cel.position)
        copied.opacity = cel.opacity
        copied.zIndex = cel.zIndex
        copy_fields(cel, copied)
      end
    end
    return target
  end
  app.transaction("MCP copy layer tree", function() clone(source_layer, target_parent, true) end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  donor:close(); sprite:close()
  return result
end
