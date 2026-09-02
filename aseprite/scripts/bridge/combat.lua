-- Beat-'em-up combat metadata stored as versioned JSON on the sprite.

local COMBAT_PROPERTY = "mcp.combat_data"

local function read_combat_data(sprite)
  local empty = {schema_version=2, boxes={}, anchors={}, actions={}, cancel_windows={},
    root_motion={}, stage_zones={}}
  local encoded = sprite.properties[COMBAT_PROPERTY]
  if type(encoded) ~= "string" or encoded == "" then return empty end
  local ok, value = pcall(json.decode, encoded)
  if not ok or type(value) ~= "table" then
    fail("INVALID_COMBAT_DATA", "sprite combat metadata is not valid JSON")
  end
  if value.schema_version ~= 1 and value.schema_version ~= 2 then
    fail("INVALID_COMBAT_DATA", "unsupported combat metadata schema version")
  end
  value.schema_version = 2
  value.boxes = value.boxes or {}
  value.anchors = value.anchors or {}
  value.actions = value.actions or {}
  value.cancel_windows = value.cancel_windows or {}
  value.root_motion = value.root_motion or {}
  value.stage_zones = value.stage_zones or {}
  return value
end

local function combat_key(value, anchor)
  return value.action_tag .. "\0" .. tostring(value.frame) .. "\0" ..
    (anchor and value.name or value.id)
end

local function validate_combat_frame(sprite, action_tag, frame)
  if frame < 0 or frame >= #sprite.frames then
    fail("INVALID_SELECTOR", "combat metadata frame is outside the sprite")
  end
  local tag = find_tag(sprite, action_tag)
  if tag == nil then fail("INVALID_SELECTOR", "combat action tag was not found: " .. action_tag) end
  local number = frame + 1
  if number < tag.fromFrame.frameNumber or number > tag.toFrame.frameNumber then
    fail("INVALID_SELECTOR", "combat metadata frame is outside its action tag")
  end
end

local function apply_combat_operations(sprite, values, operations, anchor)
  local indexed = {}
  for _, value in ipairs(values) do indexed[combat_key(value, anchor)] = value end
  for _, operation in ipairs(operations) do
    validate_combat_frame(sprite, operation.action_tag, operation.frame)
    local key = combat_key(operation, anchor)
    if operation.action == "remove" then
      indexed[key] = nil
    elseif operation.action == "set" then
      if anchor then
        if operation.x == nil or operation.y == nil then
          fail("INVALID_INPUT", "set anchor operations require x and y")
        end
        indexed[key] = {
          name=operation.name, action_tag=operation.action_tag, frame=operation.frame,
          x=operation.x, y=operation.y
        }
      else
        if operation.kind == nil or operation.bounds == nil then
          fail("INVALID_INPUT", "set combat-box operations require kind and bounds")
        end
        indexed[key] = {
          id=operation.id, action_tag=operation.action_tag, frame=operation.frame,
          kind=operation.kind, bounds=operation.bounds, damage=operation.damage,
          hitstop_ms=operation.hitstop_ms, hitstun_ms=operation.hitstun_ms,
          knockback_x=operation.knockback_x or 0, knockback_y=operation.knockback_y or 0,
          priority=operation.priority or 0, enabled=operation.enabled ~= false
        }
      end
    else fail("INVALID_INPUT", "unsupported combat metadata edit action") end
  end
  local result = {}
  for _, value in pairs(indexed) do table.insert(result, value) end
  table.sort(result, function(a, b) return combat_key(a, anchor) < combat_key(b, anchor) end)
  return result
end

operations.edit_combat_boxes = function(input)
  local sprite = open_sprite(input.source_path)
  local data = read_combat_data(sprite)
  app.transaction("MCP edit combat boxes", function()
    data.boxes = apply_combat_operations(sprite, data.boxes, input.operations, false)
    sprite.properties[COMBAT_PROPERTY] = json.encode(data)
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.edit_frame_anchors = function(input)
  local sprite = open_sprite(input.source_path)
  local data = read_combat_data(sprite)
  app.transaction("MCP edit frame anchors", function()
    data.anchors = apply_combat_operations(sprite, data.anchors, input.operations, true)
    sprite.properties[COMBAT_PROPERTY] = json.encode(data)
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

local function indexed_values(values, key_name)
  local indexed = {}
  for _, value in ipairs(values) do indexed[value[key_name]] = value end
  return indexed
end

local function sorted_values(indexed, key_name)
  local result = {}
  for _, value in pairs(indexed) do table.insert(result, value) end
  table.sort(result, function(a, b) return a[key_name] < b[key_name] end)
  return result
end

operations.edit_action_metadata = function(input)
  local sprite = open_sprite(input.source_path)
  local data = read_combat_data(sprite)
  local indexed = indexed_values(data.actions, "action_tag")
  for _, operation in ipairs(input.operations) do
    if find_tag(sprite, operation.action_tag) == nil then
      fail("INVALID_SELECTOR", "action tag was not found: " .. operation.action_tag)
    end
    if operation.action == "remove" then indexed[operation.action_tag] = nil
    elseif operation.action == "set" then
      if operation.action_type == nil then
        fail("INVALID_INPUT", "set action-metadata operations require action_type")
      end
      if operation.next_action ~= nil and find_tag(sprite, operation.next_action) == nil then
        fail("INVALID_SELECTOR", "next action tag was not found: " .. operation.next_action)
      end
      if operation.landing_action ~= nil and find_tag(sprite, operation.landing_action) == nil then
        fail("INVALID_SELECTOR", "landing action tag was not found: " .. operation.landing_action)
      end
      indexed[operation.action_tag] = {
        action_tag=operation.action_tag, action_type=operation.action_type,
        facing_policy=operation.facing_policy, movement_mode=operation.movement_mode,
        next_action=operation.next_action, landing_action=operation.landing_action,
        speed_multiplier=operation.speed_multiplier, can_turn=operation.can_turn
      }
    else fail("INVALID_INPUT", "unsupported action-metadata edit action") end
  end
  app.transaction("MCP edit action metadata", function()
    data.actions = sorted_values(indexed, "action_tag")
    sprite.properties[COMBAT_PROPERTY] = json.encode(data)
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.edit_cancel_windows = function(input)
  local sprite = open_sprite(input.source_path)
  local data = read_combat_data(sprite)
  local indexed = indexed_values(data.cancel_windows, "id")
  for _, operation in ipairs(input.operations) do
    if operation.action == "remove" then indexed[operation.id] = nil
    elseif operation.action == "set" then
      if operation.action_tag == nil or operation.from_frame == nil or
         operation.to_frame == nil then
        fail("INVALID_INPUT", "set cancel-window operations require action_tag and frame range")
      end
      local tag = find_tag(sprite, operation.action_tag)
      if tag == nil then
        fail("INVALID_SELECTOR", "action tag was not found: " .. operation.action_tag)
      end
      if operation.from_frame > operation.to_frame or
         operation.from_frame + 1 < tag.fromFrame.frameNumber or
         operation.to_frame + 1 > tag.toFrame.frameNumber then
        fail("INVALID_SELECTOR", "cancel window must stay inside its action tag")
      end
      if #operation.targets == 0 then fail("INVALID_INPUT", "cancel window requires a target") end
      for _, target in ipairs(operation.targets) do
        if find_tag(sprite, target) == nil then
          fail("INVALID_SELECTOR", "cancel target tag was not found: " .. target)
        end
      end
      indexed[operation.id] = {
        id=operation.id, action_tag=operation.action_tag,
        from_frame=operation.from_frame, to_frame=operation.to_frame,
        targets=operation.targets, on_hit=operation.on_hit, on_block=operation.on_block,
        on_whiff=operation.on_whiff, resource_cost=operation.resource_cost
      }
    else fail("INVALID_INPUT", "unsupported cancel-window edit action") end
  end
  app.transaction("MCP edit cancel windows", function()
    data.cancel_windows = sorted_values(indexed, "id")
    sprite.properties[COMBAT_PROPERTY] = json.encode(data)
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

local function root_motion_key(value)
  return value.action_tag .. "\0" .. string.format("%08d", value.frame)
end

operations.edit_root_motion = function(input)
  local sprite = open_sprite(input.source_path)
  local data = read_combat_data(sprite)
  local indexed = {}
  for _, value in ipairs(data.root_motion) do indexed[root_motion_key(value)] = value end
  for _, operation in ipairs(input.operations) do
    validate_combat_frame(sprite, operation.action_tag, operation.frame)
    local key = root_motion_key(operation)
    if operation.action == "remove" then indexed[key] = nil
    elseif operation.action == "set" then
      indexed[key] = {action_tag=operation.action_tag, frame=operation.frame,
        delta_x=operation.delta_x, delta_y=operation.delta_y,
        delta_lane=operation.delta_lane}
    else fail("INVALID_INPUT", "unsupported root-motion edit action") end
  end
  local values = {}
  for _, value in pairs(indexed) do table.insert(values, value) end
  table.sort(values, function(a, b) return root_motion_key(a) < root_motion_key(b) end)
  app.transaction("MCP edit root motion", function()
    data.root_motion = values
    sprite.properties[COMBAT_PROPERTY] = json.encode(data)
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.edit_stage_gameplay_zones = function(input)
  local sprite = open_sprite(input.source_path)
  local data = read_combat_data(sprite)
  local indexed = indexed_values(data.stage_zones, "id")
  for _, operation in ipairs(input.operations) do
    if operation.action == "remove" then indexed[operation.id] = nil
    elseif operation.action == "set" then
      if operation.kind == nil or operation.bounds == nil then
        fail("INVALID_INPUT", "set stage-zone operations require kind and bounds")
      end
      local bounds = operation.bounds
      if bounds.x < 0 or bounds.y < 0 or
         bounds.x + bounds.width > sprite.width or bounds.y + bounds.height > sprite.height then
        fail("INVALID_SELECTOR", "stage gameplay zone is outside the sprite canvas")
      end
      indexed[operation.id] = {id=operation.id, kind=operation.kind, bounds=bounds,
        target=operation.target, order=operation.order, enabled=operation.enabled}
    else fail("INVALID_INPUT", "unsupported stage-zone edit action") end
  end
  app.transaction("MCP edit stage gameplay zones", function()
    data.stage_zones = sorted_values(indexed, "id")
    sprite.properties[COMBAT_PROPERTY] = json.encode(data)
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

local function action_combat_data(sprite, action_tag)
  local tag = find_tag(sprite, action_tag)
  if tag == nil then fail("INVALID_SELECTOR", "combat action tag was not found: " .. action_tag) end
  local data = read_combat_data(sprite)
  local boxes, anchors = {}, {}
  for _, box in ipairs(data.boxes) do
    if box.action_tag == action_tag then table.insert(boxes, box) end
  end
  for _, anchor in ipairs(data.anchors) do
    if anchor.action_tag == action_tag then table.insert(anchors, anchor) end
  end
  return tag, boxes, anchors
end

local function validate_combat_action_data(sprite, input)
  local tag, boxes, anchors = action_combat_data(sprite, input.action_tag)
  local first, last = tag.fromFrame.frameNumber - 1, tag.toFrame.frameNumber - 1
  local issues, active, active_set = {}, {}, {}
  local hurt_frames, anchor_frames = {}, {}
  for _, box in ipairs(boxes) do
    if box.frame < first or box.frame > last then
      table.insert(issues, {code="BOX_OUTSIDE_ACTION", severity="error",
        message="combat box is outside the action tag", frames={box.frame}})
    end
    if box.enabled ~= false and (box.kind == "hit" or box.kind == "grab" or box.kind == "throw") then
      active_set[box.frame] = true
      if box.kind == "hit" and box.damage == nil then
        table.insert(issues, {code="HITBOX_MISSING_DAMAGE", severity="warning",
          message="hit box has no damage value", frames={box.frame}})
      end
    end
    if box.enabled ~= false and box.kind == "hurt" then hurt_frames[box.frame] = true end
  end
  for _, anchor in ipairs(anchors) do
    anchor_frames[anchor.name] = anchor_frames[anchor.name] or {}
    anchor_frames[anchor.name][anchor.frame] = true
  end
  for frame = first, last do
    if input.require_hurtbox and not hurt_frames[frame] then
      table.insert(issues, {code="MISSING_HURTBOX", severity="error",
        message="action frame has no enabled hurt box", frames={frame}})
    end
    for _, name in ipairs(input.required_anchors) do
      if anchor_frames[name] == nil or not anchor_frames[name][frame] then
        table.insert(issues, {code="MISSING_ANCHOR", severity="error",
          message="action frame is missing required anchor: " .. name, frames={frame}})
      end
    end
    if active_set[frame] then table.insert(active, frame) end
  end
  if input.require_active_frames and #active == 0 then
    table.insert(issues, {code="NO_ACTIVE_FRAMES", severity="error",
      message="action has no enabled hit, grab, or throw boxes", frames={}})
  end
  local first_active, last_active = active[1], active[#active]
  local startup = first_active and (first_active - first) or (last - first + 1)
  local recovery = last_active and (last - last_active) or 0
  local valid = true
  for _, issue in ipairs(issues) do if issue.severity == "error" then valid = false end end
  return {source_path=input.source_path, action_tag=input.action_tag, valid=valid,
    from_frame=first, to_frame=last, startup_frames=startup, active_frames=active,
    recovery_frames=recovery, boxes=boxes, anchors=anchors, issues=issues}
end

operations.validate_combat_action = function(input)
  local sprite = open_sprite(input.source_path)
  local result = validate_combat_action_data(sprite, input)
  sprite:close()
  return result
end

operations.validate_combat_set = function(input)
  local sprite = open_sprite(input.source_path)
  local data = read_combat_data(sprite)
  local selected, selected_set, missing_authored = {}, {}, {}
  if #input.action_tags > 0 then
    for _, name in ipairs(input.action_tags) do
      if selected_set[name] then fail("INVALID_INPUT", "action_tags must not contain duplicates") end
      if find_tag(sprite, name) == nil then fail("INVALID_SELECTOR", "action tag was not found: " .. name) end
      selected_set[name] = true
      table.insert(selected, name)
    end
  elseif #data.actions > 0 then
    for _, metadata in ipairs(data.actions) do
      if find_tag(sprite, metadata.action_tag) == nil then
        table.insert(missing_authored, metadata.action_tag)
      else
        selected_set[metadata.action_tag] = true
        table.insert(selected, metadata.action_tag)
      end
    end
  else
    for _, tag in ipairs(sprite.tags) do
      selected_set[tag.name] = true
      table.insert(selected, tag.name)
    end
  end
  table.sort(selected)
  local results, issues = {}, {}
  for _, name in ipairs(missing_authored) do
    table.insert(issues, {code="MISSING_ACTION_TAG", severity="error",
      message="action metadata references a missing tag: " .. name, frames={}})
  end
  if #selected == 0 then
    table.insert(issues, {code="NO_ACTIONS", severity="error",
      message="no action tags were selected or authored", frames={}})
  end
  local metadata_set = {}
  for _, metadata in ipairs(data.actions) do metadata_set[metadata.action_tag] = true end
  for _, name in ipairs(selected) do
    local result = validate_combat_action_data(sprite, {
      source_path=input.source_path, action_tag=name,
      require_hurtbox=input.require_hurtbox,
      require_active_frames=input.require_active_frames,
      required_anchors=input.required_anchors
    })
    table.insert(results, result)
    if input.require_action_metadata and not metadata_set[name] then
      table.insert(issues, {code="MISSING_ACTION_METADATA", severity="error",
        message="action is missing action metadata: " .. name, frames={}})
    end
  end
  for _, window in ipairs(data.cancel_windows) do
    local source_tag = find_tag(sprite, window.action_tag)
    if source_tag == nil then
      table.insert(issues, {code="MISSING_CANCEL_SOURCE", severity="error",
        message="cancel window references a missing source action: " .. window.action_tag,
        frames={window.from_frame, window.to_frame}})
    elseif selected_set[window.action_tag] then
      if window.from_frame + 1 < source_tag.fromFrame.frameNumber or
         window.to_frame + 1 > source_tag.toFrame.frameNumber or
         window.from_frame > window.to_frame then
        table.insert(issues, {code="INVALID_CANCEL_WINDOW", severity="error",
          message="cancel window is outside its action tag: " .. window.id,
          frames={window.from_frame, window.to_frame}})
      end
      for _, target in ipairs(window.targets) do
        if find_tag(sprite, target) == nil then
          table.insert(issues, {code="MISSING_CANCEL_TARGET", severity="error",
            message="cancel window references a missing action: " .. target,
            frames={window.from_frame, window.to_frame}})
        end
      end
    end
  end
  for _, metadata in ipairs(data.actions) do
    local transitions = {}
    if metadata.next_action ~= nil then table.insert(transitions, metadata.next_action) end
    if metadata.landing_action ~= nil then table.insert(transitions, metadata.landing_action) end
    for _, target in ipairs(transitions) do
      if find_tag(sprite, target) == nil then
        table.insert(issues, {code="MISSING_ACTION_TRANSITION", severity="error",
          message="action metadata references a missing transition: " .. target, frames={}})
      end
    end
  end
  for _, motion in ipairs(data.root_motion) do
    if selected_set[motion.action_tag] then
      local tag = find_tag(sprite, motion.action_tag)
      if tag == nil or motion.frame + 1 < tag.fromFrame.frameNumber or
         motion.frame + 1 > tag.toFrame.frameNumber then
        table.insert(issues, {code="ROOT_MOTION_OUTSIDE_ACTION", severity="error",
          message="root motion is outside its action tag", frames={motion.frame}})
      end
    end
  end
  local valid = true
  for _, result in ipairs(results) do if not result.valid then valid = false end end
  for _, issue in ipairs(issues) do if issue.severity == "error" then valid = false end end
  sprite:close()
  return {source_path=input.source_path, valid=valid, actions=results, issues=issues}
end

local COMBAT_COLORS = {
  hurt=Color{r=64,g=160,b=255,a=255}, hit=Color{r=255,g=64,b=64,a=255},
  push=Color{r=255,g=220,b=64,a=255}, grab=Color{r=255,g=80,b=220,a=255},
  throw=Color{r=255,g=128,b=32,a=255}, armor=Color{r=160,g=96,b=255,a=255},
  invulnerable=Color{r=64,g=255,b=160,a=255}
}

local function draw_outline(image, bounds, color)
  local left, top = bounds.x, bounds.y
  local right, bottom = bounds.x + bounds.width - 1, bounds.y + bounds.height - 1
  for x = left, right do
    if x >= 0 and x < image.width then
      if top >= 0 and top < image.height then image:drawPixel(x, top, color) end
      if bottom >= 0 and bottom < image.height then image:drawPixel(x, bottom, color) end
    end
  end
  for y = top, bottom do
    if y >= 0 and y < image.height then
      if left >= 0 and left < image.width then image:drawPixel(left, y, color) end
      if right >= 0 and right < image.width then image:drawPixel(right, y, color) end
    end
  end
end

local function combat_overlay_image(sprite, boxes, anchors, frame, kinds, scale)
  local image = Image(sprite.width, sprite.height, ColorMode.RGB)
  image:clear()
  image:drawSprite(sprite, frame + 1, Point(0, 0))
  for _, box in ipairs(boxes) do
    if box.frame == frame and box.enabled ~= false and
       (kinds == nil or kinds[box.kind] == true) then
      draw_outline(image, box.bounds, COMBAT_COLORS[box.kind] or Color{r=255,g=255,b=255,a=255})
    end
  end
  for _, anchor in ipairs(anchors) do
    if anchor.frame == frame then
      local color = Color{r=255,g=255,b=255,a=255}
      for offset = -2, 2 do
        if anchor.x + offset >= 0 and anchor.x + offset < image.width and
           anchor.y >= 0 and anchor.y < image.height then
          image:drawPixel(anchor.x + offset, anchor.y, color)
        end
        if anchor.x >= 0 and anchor.x < image.width and
           anchor.y + offset >= 0 and anchor.y + offset < image.height then
          image:drawPixel(anchor.x, anchor.y + offset, color)
        end
      end
    end
  end
  if scale > 1 then image:resize(image.width * scale, image.height * scale) end
  return image
end

operations.preview_combat_overlay = function(input)
  local sprite = open_sprite(input.source_path)
  local _, boxes, anchors = action_combat_data(sprite, input.action_tag)
  local frame_number = input.frame + 1
  if frame_number < 1 or frame_number > #sprite.frames then
    fail("INVALID_SELECTOR", "preview frame is outside the sprite")
  end
  local image = combat_overlay_image(sprite, boxes, anchors, input.frame, input.kinds, input.scale)
  if image.width * image.height > input.max_pixels then
    fail("LIMIT_EXCEEDED", "combat overlay preview exceeds the pixel limit")
  end
  image:saveAs(input.output_path)
  local result = {width=image.width, height=image.height, box_count=#boxes, anchor_count=#anchors}
  sprite:close()
  return result
end

operations.preview_combat_animation = function(input)
  local sprite = open_sprite(input.source_path)
  local tag, boxes, anchors = action_combat_data(sprite, input.action_tag)
  local count = tag.toFrame.frameNumber - tag.fromFrame.frameNumber + 1
  local width, height = sprite.width * input.scale, sprite.height * input.scale
  if width * height * count > input.max_pixels then
    fail("LIMIT_EXCEEDED", "animated combat preview exceeds the pixel limit")
  end
  local preview = Sprite(width, height, ColorMode.RGB)
  local layer = preview.layers[1]
  for index = 1, count do
    if index > 1 then preview:newFrame() end
    local source_frame = tag.fromFrame.frameNumber + index - 1
    local image = combat_overlay_image(
      sprite, boxes, anchors, source_frame - 1, input.kinds, input.scale
    )
    local cel = layer:cel(index)
    if cel ~= nil then cel.image = image
    else preview:newCel(layer, index, image, Point(0, 0)) end
    preview.frames[index].duration = sprite.frames[source_frame].duration
  end
  save_copy(preview, input.output_path)
  local result = {frame_count=count, width=width, height=height}
  preview:close()
  sprite:close()
  return result
end

local function zone_contains(zone, x, y)
  return x >= zone.bounds.x and y >= zone.bounds.y and
    x < zone.bounds.x + zone.bounds.width and y < zone.bounds.y + zone.bounds.height
end

operations.validate_stage_gameplay = function(input)
  local sprite = open_sprite(input.source_path)
  local data = read_combat_data(sprite)
  local zones, walkable, issues = {}, {}, {}
  local spawn_count, exit_count, camera_count = 0, 0, 0
  local encounter_orders = {}
  for _, zone in ipairs(data.stage_zones) do
    if zone.enabled ~= false then
      table.insert(zones, zone)
      if zone.bounds.x < 0 or zone.bounds.y < 0 or
         zone.bounds.x + zone.bounds.width > sprite.width or
         zone.bounds.y + zone.bounds.height > sprite.height then
        table.insert(issues, {code="ZONE_OUTSIDE_CANVAS", severity="error",
          message="stage gameplay zone is outside the canvas: " .. zone.id, frames={}})
      end
      if zone.kind == "walkable" then table.insert(walkable, zone) end
      if zone.kind == "spawn" then spawn_count = spawn_count + 1 end
      if zone.kind == "exit" then
        exit_count = exit_count + 1
        if zone.target == nil then
          table.insert(issues, {code="EXIT_MISSING_TARGET", severity="warning",
            message="exit zone has no target: " .. zone.id, frames={}})
        end
      end
      if zone.kind == "camera" then camera_count = camera_count + 1 end
      if zone.kind == "encounter" then
        if encounter_orders[zone.order] ~= nil then
          table.insert(issues, {code="DUPLICATE_ENCOUNTER_ORDER", severity="warning",
            message="encounter zones share order " .. tostring(zone.order), frames={}})
        end
        encounter_orders[zone.order] = zone.id
      end
    end
  end
  if #walkable == 0 then
    table.insert(issues, {code="MISSING_WALKABLE_ZONE", severity="error",
      message="stage has no enabled walkable zone", frames={}})
  end
  if input.require_spawn and spawn_count == 0 then
    table.insert(issues, {code="MISSING_SPAWN", severity="error",
      message="stage has no enabled spawn zone", frames={}})
  end
  if input.require_exit and exit_count == 0 then
    table.insert(issues, {code="MISSING_EXIT", severity="error",
      message="stage has no enabled exit zone", frames={}})
  end
  if input.require_camera and camera_count == 0 then
    table.insert(issues, {code="MISSING_CAMERA_ZONE", severity="error",
      message="stage has no enabled camera zone", frames={}})
  end
  for _, zone in ipairs(zones) do
    if zone.kind == "spawn" or zone.kind == "exit" or zone.kind == "encounter" then
      local center_x = zone.bounds.x + math.floor(zone.bounds.width / 2)
      local center_y = zone.bounds.y + math.floor(zone.bounds.height / 2)
      local inside = false
      for _, floor in ipairs(walkable) do
        if zone_contains(floor, center_x, center_y) then inside = true; break end
      end
      if not inside then
        table.insert(issues, {code="ZONE_OUTSIDE_WALKABLE", severity="error",
          message=zone.kind .. " zone is not centered in a walkable zone: " .. zone.id,
          frames={}})
      end
    end
  end
  local valid = true
  for _, issue in ipairs(issues) do if issue.severity == "error" then valid = false end end
  sprite:close()
  return {source_path=input.source_path, valid=valid, zones=zones, issues=issues}
end

operations.inspect_combat_manifest = function(input)
  local sprite = open_sprite(input.source_path)
  local data = read_combat_data(sprite)
  local tags, durations, events = {}, {}, {}
  for _, tag in ipairs(sprite.tags) do
    if input.action_tag == nil or tag.name == input.action_tag then
      table.insert(tags, {name=tag.name, from_frame=tag.fromFrame.frameNumber - 1,
        to_frame=tag.toFrame.frameNumber - 1, direction=animation_direction_name(tag.aniDir),
        repeats=tag.repeats or 0})
    end
  end
  if input.action_tag ~= nil and #tags == 0 then
    fail("INVALID_SELECTOR", "combat action tag was not found: " .. input.action_tag)
  end
  for _, frame in ipairs(sprite.frames) do
    table.insert(durations, math.floor(frame.duration * 1000 + 0.5))
  end
  local encoded_events = sprite.properties["mcp.animation_events"]
  if type(encoded_events) == "string" and encoded_events ~= "" then
    local ok, value = pcall(json.decode, encoded_events)
    if ok and type(value) == "table" then
      if input.action_tag == nil then events = value
      else
        for _, event in ipairs(value) do
          if event.frame >= tags[1].from_frame and event.frame <= tags[1].to_frame then
            table.insert(events, event)
          end
        end
      end
    end
  end
  local boxes, anchors = {}, {}
  for _, box in ipairs(data.boxes) do
    if input.action_tag == nil or box.action_tag == input.action_tag then table.insert(boxes, box) end
  end
  for _, anchor in ipairs(data.anchors) do
    if input.action_tag == nil or anchor.action_tag == input.action_tag then table.insert(anchors, anchor) end
  end
  local action_metadata, cancel_windows, root_motion = {}, {}, {}
  for _, metadata in ipairs(data.actions) do
    if input.action_tag == nil or metadata.action_tag == input.action_tag then
      table.insert(action_metadata, metadata)
    end
  end
  for _, window in ipairs(data.cancel_windows) do
    if input.action_tag == nil or window.action_tag == input.action_tag then
      table.insert(cancel_windows, window)
    end
  end
  for _, motion in ipairs(data.root_motion) do
    if input.action_tag == nil or motion.action_tag == input.action_tag then
      table.insert(root_motion, motion)
    end
  end
  local stage_zones = input.action_tag == nil and data.stage_zones or {}
  local sprite_info = {width=sprite.width, height=sprite.height,
    color_mode=color_mode_name(sprite.colorMode), frame_count=#durations, durations_ms=durations}
  sprite:close()
  return {schema="aseprite-mcp-combat", schema_version=2, source_path=input.source_path,
    sprite={width=sprite_info.width, height=sprite_info.height, color_mode=sprite_info.color_mode,
      frame_count=#durations, durations_ms=durations}, actions=tags, boxes=boxes,
    anchors=anchors, events=events, action_metadata=action_metadata,
    cancel_windows=cancel_windows, root_motion=root_motion,
    stage_zones=stage_zones}
end

operations.inspect_combat_character = function(input)
  local sprite = open_sprite(input.source_path)
  local data = read_combat_data(sprite)
  local actions, anchor_names, seen = {}, {}, {}
  for _, tag in ipairs(sprite.tags) do table.insert(actions, tag.name) end
  for _, anchor in ipairs(data.anchors) do
    if not seen[anchor.name] then seen[anchor.name] = true; table.insert(anchor_names, anchor.name) end
  end
  table.sort(actions); table.sort(anchor_names)
  local result = {source_path=input.source_path, width=sprite.width, height=sprite.height,
    color_mode=color_mode_name(sprite.colorMode), actions=actions, anchor_names=anchor_names}
  sprite:close()
  return result
end
