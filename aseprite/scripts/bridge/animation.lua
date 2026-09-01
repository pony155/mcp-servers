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

operations.edit_animation_events = function(input)
  local sprite=open_sprite(input.source_path);local events={}
  local encoded=sprite.properties["mcp.animation_events"]
  if type(encoded)=="string" and encoded~="" then local ok,value=pcall(json.decode,encoded)
    if ok and type(value)=="table" then events=value end end
  app.transaction("MCP edit animation events",function()
    for _,operation in ipairs(input.operations) do
      if operation.frame>=#sprite.frames then fail("INVALID_SELECTOR","event frame is outside the sprite") end
      if operation.layer~=nil then find_layer(sprite,operation.layer) end
      local found=nil
      for index,event in ipairs(events) do if event.name==operation.name and
        event.frame==operation.frame and event.layer==operation.layer then found=index;break end end
      if operation.action=="remove" then if found~=nil then table.remove(events,found) end
      else local event={name=operation.name,frame=operation.frame,layer=operation.layer,data=operation.data}
        if found~=nil then events[found]=event else table.insert(events,event) end end
    end
    table.sort(events,function(a,b)
      if a.frame~=b.frame then return a.frame<b.frame end
      if a.name~=b.name then return a.name<b.name end
      return tostring(a.layer or "")<tostring(b.layer or "")
    end)
    sprite.properties["mcp.animation_events"]=json.encode(events)
  end)
  save_copy(sprite,input.output_path)
  local result=inspect_sprite(sprite,false,input.output_path);sprite:close();return result
end

local function tween_canvas(sprite, cel)
  local image = Image(sprite.spec)
  image:clear()
  image:drawImage(cel.image, cel.position, cel.opacity)
  return image
end

operations.generate_inbetweens = function(input)
  local sprite = open_sprite(input.source_path)
  if #sprite.frames + input.count > input.max_frames then
    fail("LIMIT_EXCEEDED", "generated frame count exceeds the limit")
  end
  local layer = find_layer(sprite, input.layer)
  if layer.isGroup or layer.isTilemap or layer.isBackground then
    fail("INVALID_SELECTOR", "inbetweens require a transparent image layer")
  end
  local first_number, last_number = input.first_frame + 1, input.last_frame + 1
  if first_number < 1 or last_number > #sprite.frames or first_number >= last_number then
    fail("INVALID_SELECTOR", "inbetween endpoints are outside or out of order")
  end
  local first_cel, last_cel = layer:cel(first_number), layer:cel(last_number)
  if first_cel == nil or last_cel == nil then
    fail("INVALID_SELECTOR", "both endpoint cels must exist on the selected layer")
  end
  local first_image, last_image = Image(first_cel.image), Image(last_cel.image)
  local first_position, last_position = first_cel.position, last_cel.position
  local first_opacity, last_opacity = first_cel.opacity, last_cel.opacity
  local tween_duration = (sprite.frames[first_number].duration +
    sprite.frames[last_number].duration) / 2
  local first_canvas, last_canvas = nil, nil
  if input.interpolation == "crossfade" then
    if sprite.width * sprite.height * input.count > input.max_pixel_visits then
      fail("LIMIT_EXCEEDED", "inbetween generation exceeds the pixel visit limit")
    end
    first_canvas, last_canvas = tween_canvas(sprite, first_cel), tween_canvas(sprite, last_cel)
  end
  app.transaction("MCP generate inbetweens", function()
    for index = 1, input.count do
      local amount = index / (input.count + 1)
      local new_frame = sprite:newFrame(input.first_frame + index)
      local cel = layer:cel(new_frame)
      if cel == nil then fail("ASEPRITE_FAILED", "duplicated frame did not contain the target cel") end
      cel.opacity = math.floor(first_opacity + (last_opacity - first_opacity) * amount + 0.5)
      if input.interpolation == "crossfade" then
        local image = Image(sprite.spec)
        image:clear()
        for y = 0, sprite.height - 1 do
          for x = 0, sprite.width - 1 do
            local ar, ag, ab, aa = pixel_rgba(sprite, nil, first_canvas:getPixel(x, y))
            local br, bg, bb, ba = pixel_rgba(sprite, nil, last_canvas:getPixel(x, y))
            image:drawPixel(x, y, Color {
              r = math.floor(ar + (br - ar) * amount + 0.5),
              g = math.floor(ag + (bg - ag) * amount + 0.5),
              b = math.floor(ab + (bb - ab) * amount + 0.5),
              a = math.floor(aa + (ba - aa) * amount + 0.5)
            })
          end
        end
        cel.image, cel.position, cel.opacity = image, Point(0, 0), 255
      else
        local use_last = input.interpolation == "nearest" and amount >= 0.5
        cel.image = Image(use_last and last_image or first_image)
        cel.position = Point(
          math.floor(first_position.x + (last_position.x - first_position.x) * amount + 0.5),
          math.floor(first_position.y + (last_position.y - first_position.y) * amount + 0.5)
        )
      end
      new_frame.duration = tween_duration
    end
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

local function tinted_frame(sprite, frame, red, green, blue)
  local source = render_frame_image(sprite, frame)
  local target = Image(sprite.width, sprite.height, ColorMode.RGB)
  target:clear()
  for y = 0, sprite.height - 1 do
    for x = 0, sprite.width - 1 do
      local _, _, _, alpha = pixel_rgba(sprite, nil, source:getPixel(x, y))
      if alpha > 0 then target:drawPixel(x, y, Color {r=red, g=green, b=blue, a=alpha}) end
    end
  end
  return target
end

operations.preview_onion_skin = function(input)
  local sprite = open_sprite(input.source_path)
  local current = input.frame + 1
  if current < 1 or current > #sprite.frames then
    fail("INVALID_SELECTOR", "onion-skin frame is outside the sprite")
  end
  local width, height = sprite.width * input.scale, sprite.height * input.scale
  if width * height > input.max_pixels then
    fail("LIMIT_EXCEEDED", "onion-skin preview exceeds the pixel limit")
  end
  local preview = Image(sprite.width, sprite.height, ColorMode.RGB)
  preview:clear()
  for frame = math.max(1, current - input.before), current - 1 do
    preview:drawImage(tinted_frame(sprite, frame, 255, 64, 64), Point(0, 0), input.opacity)
  end
  for frame = math.min(#sprite.frames, current + input.after), current + 1, -1 do
    preview:drawImage(tinted_frame(sprite, frame, 64, 128, 255), Point(0, 0), input.opacity)
  end
  local active = render_frame_image(sprite, current)
  preview:drawImage(active)
  if input.scale > 1 then preview:resize(width, height) end
  preview:saveAs(input.output_path)
  sprite:close()
  return {width=width, height=height}
end

local function retime_weight(distribution, index, count, current)
  if distribution == "preserve" then return current end
  if distribution == "uniform" then return 1 end
  if distribution == "ease_in" then return index end
  if distribution == "ease_out" then return count - index + 1 end
  if distribution == "ease_in_out" then return math.min(index, count - index + 1) end
  fail("INVALID_INPUT", "unsupported timing distribution")
end

operations.retime_animation = function(input)
  local sprite = open_sprite(input.source_path)
  local first, last = 1, #sprite.frames
  if input.tag ~= nil then
    local tag = find_tag(sprite, input.tag)
    if tag == nil then fail("INVALID_SELECTOR", "animation tag was not found") end
    first, last = tag.fromFrame.frameNumber, tag.toFrame.frameNumber
  end
  local count, current_total = last - first + 1, 0
  for frame = first, last do
    current_total = current_total + math.floor(sprite.frames[frame].duration * 1000 + 0.5)
  end
  local target_total
  if input.mode == "fps" then target_total = math.floor(count * 1000 / input.target_fps + 0.5)
  elseif input.mode == "total_duration" then target_total = input.target_total_duration_ms
  elseif input.mode == "scale" then target_total = math.floor(current_total * input.scale + 0.5)
  else fail("INVALID_INPUT", "unsupported retiming mode") end
  if target_total < count then fail("INVALID_INPUT", "target duration is shorter than one millisecond per frame") end
  local weights, weight_total = {}, 0
  for index = 1, count do
    local current = math.floor(sprite.frames[first + index - 1].duration * 1000 + 0.5)
    weights[index] = retime_weight(input.distribution, index, count, current)
    weight_total = weight_total + weights[index]
  end
  local durations, assigned = {}, 0
  for index = 1, count do
    durations[index] = math.max(1, math.floor(target_total * weights[index] / weight_total))
    assigned = assigned + durations[index]
  end
  local cursor = 1
  while assigned < target_total do
    durations[cursor] = durations[cursor] + 1; assigned = assigned + 1
    cursor = cursor % count + 1
  end
  cursor = count
  while assigned > target_total do
    if durations[cursor] > 1 then durations[cursor] = durations[cursor] - 1; assigned = assigned - 1 end
    cursor = (cursor - 2) % count + 1
  end
  app.transaction("MCP retime animation", function()
    for index = 1, count do sprite.frames[first + index - 1].duration = durations[index] / 1000 end
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

local function directed_tag_frames(tag)
  local first, last = tag.fromFrame.frameNumber, tag.toFrame.frameNumber
  local result = {}
  if tag.aniDir == AniDir.REVERSE or tag.aniDir == AniDir.PING_PONG_REVERSE then
    for frame = last, first, -1 do table.insert(result, frame) end
    if tag.aniDir == AniDir.PING_PONG_REVERSE then
      for frame = first + 1, last - 1 do table.insert(result, frame) end
    end
  else
    for frame = first, last do table.insert(result, frame) end
    if tag.aniDir == AniDir.PING_PONG then
      for frame = last - 1, first + 1, -1 do table.insert(result, frame) end
    end
  end
  return result
end

operations.bake_tag_direction = function(input)
  local sprite = open_sprite(input.source_path)
  local tag = find_tag(sprite, input.tag)
  if tag == nil then fail("INVALID_SELECTOR", "animation tag was not found") end
  if find_tag(sprite, input.output_tag) ~= nil then
    fail("INVALID_INPUT", "output tag already exists: " .. input.output_tag)
  end
  local sequence = directed_tag_frames(tag)
  local added = #sequence * input.repetitions
  if #sprite.frames + added > input.max_frames then fail("LIMIT_EXCEEDED", "baked sequence exceeds frame limit") end
  local source_frames = {}
  for _, frame_number in ipairs(sequence) do table.insert(source_frames, sprite.frames[frame_number]) end
  local events = {}
  local encoded_events = sprite.properties["mcp.animation_events"]
  if type(encoded_events) == "string" and encoded_events ~= "" then
    local decoded, value = pcall(json.decode, encoded_events)
    if decoded and type(value) == "table" then events = value end
  end
  local output_first = #sprite.frames + 1
  app.transaction("MCP bake tag direction", function()
    for _ = 1, input.repetitions do
      for _, source_frame in ipairs(source_frames) do
        local target_frame = sprite:newEmptyFrame()
        target_frame.duration = source_frame.duration
        local source_cels = {}
        for _, cel in ipairs(sprite.cels) do
          if cel.frame == source_frame then table.insert(source_cels, cel) end
        end
        for _, source_cel in ipairs(source_cels) do
          local image = input.link_images and source_cel.image or Image(source_cel.image)
          local target_cel = source_cel.layer:cel(target_frame)
          if target_cel ~= nil then
            target_cel.image = image; target_cel.position = source_cel.position
          else
            target_cel = sprite:newCel(
              source_cel.layer, target_frame, image, source_cel.position
            )
          end
          target_cel.opacity = source_cel.opacity
          target_cel.zIndex = source_cel.zIndex
          target_cel.data = source_cel.data
          target_cel.color = source_cel.color
          for key, value in pairs(source_cel.properties) do
            local kind = type(value)
            if kind == "string" or kind == "number" or kind == "boolean" then
              target_cel.properties[key] = value
            end
          end
        end
        local source_zero, target_zero = source_frame.frameNumber - 1,
          target_frame.frameNumber - 1
        local copied_events = {}
        for _, event in ipairs(events) do
          if event.frame == source_zero then
            table.insert(copied_events, {name=event.name, frame=target_zero,
              layer=event.layer, data=event.data})
          end
        end
        for _, event in ipairs(copied_events) do table.insert(events, event) end
      end
    end
    local baked = sprite:newTag(output_first, #sprite.frames)
    baked.name = input.output_tag
    baked.aniDir = AniDir.FORWARD
    if #events > 0 then sprite.properties["mcp.animation_events"] = json.encode(events) end
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end
