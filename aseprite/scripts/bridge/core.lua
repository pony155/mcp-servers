operations.health = function(_)
  return { aseprite_version = tostring(app.version), api_version = app.apiVersion or 0 }
end

operations.inspect = function(input)
  local sprite = open_sprite(input.source_path)
  local result = inspect_sprite(sprite, input.include_palette_colors == true, input.source_path)
  sprite:close()
  return result
end
