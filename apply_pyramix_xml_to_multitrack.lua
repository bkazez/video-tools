-- Apply Pyramix XML EDL to Reaper Multitrack
-- Reads a Pyramix XML export and applies the edit decisions to multitrack audio in Reaper
-- Requires that Reaper has regions named matching the clip names in the XML
-- Places edited multitrack audio starting at the current edit cursor position

local xml_file_path = ""  -- Will be set via command line or user prompt

function msg(text)
    reaper.ShowConsoleMsg(tostring(text) .. "\n")
end

function parse_xml_attribute(line, attr_name)
    local pattern = attr_name .. '="([^"]*)"'
    local value = line:match(pattern)
    return value
end

function parse_pyramix_xml(xml_path)
    -- Use iconv to convert UTF-16 to UTF-8 first
    local temp_file = os.tmpname()
    local convert_cmd = 'iconv -f UTF-16 -t UTF-8 "' .. xml_path .. '" > "' .. temp_file .. '"'
    local result = os.execute(convert_cmd)
    if not result then
        return nil, "Could not convert XML encoding"
    end

    local file = io.open(temp_file, "r")
    if not file then
        os.remove(temp_file)
        return nil, "Could not open XML file"
    end

    local content = file:read("*all")
    file:close()
    os.remove(temp_file)

    -- Extract sampling rate
    local sampling_rate = content:match('SamplingRateValue="(%d+)"')
    if not sampling_rate then
        return nil, "Could not find sampling rate in XML"
    end
    sampling_rate = tonumber(sampling_rate)

    -- Parse clips
    local clips = {}
    local clip_pattern = '<MTICClip[^>]+>'

    for clip_header in content:gmatch(clip_pattern) do
        local clip = {}
        clip.name = parse_xml_attribute(clip_header, "Name")
        clip.dest_in = tonumber(parse_xml_attribute(clip_header, "DestinationIn"))
        clip.source_in = tonumber(parse_xml_attribute(clip_header, "SourceIn"))
        clip.source_out = tonumber(parse_xml_attribute(clip_header, "SourceOut"))

        -- Find fade info for this clip
        local clip_start_pos = content:find(clip_header, 1, true)
        local clip_end_pos = content:find("</MTICClip>", clip_start_pos)
        if clip_start_pos and clip_end_pos then
            local clip_content = content:sub(clip_start_pos, clip_end_pos)
            local fade_in_line = clip_content:match('<FadeIn[^>]+>')
            local fade_out_line = clip_content:match('<FadeOut[^>]+>')

            if fade_in_line then
                clip.fade_in = tonumber(parse_xml_attribute(fade_in_line, "Length")) or 0
            else
                clip.fade_in = 0
            end

            if fade_out_line then
                clip.fade_out = tonumber(parse_xml_attribute(fade_out_line, "Length")) or 0
            else
                clip.fade_out = 0
            end
        end

        if clip.name and clip.dest_in and clip.source_in and clip.source_out then
            table.insert(clips, clip)
        end
    end

    return {
        sampling_rate = sampling_rate,
        clips = clips
    }, nil
end

function clean_clip_name(name)
    -- Remove " (1)" suffix that Pyramix adds
    name = name:gsub(" %(%d+%)$", "")
    -- Replace underscores with spaces to match Reaper region names
    name = name:gsub("_", " ")
    return name
end

function find_region_by_name(name)
    local num_markers, num_regions = reaper.CountProjectMarkers(0)
    local total_markers = num_markers + num_regions

    for i = 0, total_markers - 1 do
        local retval, isrgn, pos, rgnend, region_name_found, markrgnindexnumber = reaper.EnumProjectMarkers(i)
        if retval and isrgn and region_name_found == name then
            return pos, rgnend, markrgnindexnumber
        end
    end
    return nil, nil, nil
end

function get_media_items_in_region(region_start, region_end)
    local items = {}
    for trackIdx = 0, reaper.CountTracks(0) - 1 do
        local track = reaper.GetTrack(0, trackIdx)
        for itemIdx = 0, reaper.CountTrackMediaItems(track) - 1 do
            local item = reaper.GetTrackMediaItem(track, itemIdx)
            local pos = reaper.GetMediaItemInfo_Value(item, "D_POSITION")
            local length = reaper.GetMediaItemInfo_Value(item, "D_LENGTH")
            local itemEnd = pos + length

            -- Find items that overlap with the region
            if itemEnd > region_start and pos < region_end then
                items[#items + 1] = {
                    track = track,
                    item = item,
                    pos = pos,
                    length = length
                }
            end
        end
    end
    return items
end

function samples_to_seconds(samples, sample_rate)
    return samples / sample_rate
end

function apply_fades_to_item(item, fade_in_samples, fade_out_samples, sample_rate)
    if fade_in_samples > 0 then
        local fade_in_seconds = samples_to_seconds(fade_in_samples, sample_rate)
        reaper.SetMediaItemInfo_Value(item, "D_FADEINLEN", fade_in_seconds)
        reaper.SetMediaItemInfo_Value(item, "D_FADEINLEN_AUTO", fade_in_seconds)
    end

    if fade_out_samples > 0 then
        local fade_out_seconds = samples_to_seconds(fade_out_samples, sample_rate)
        reaper.SetMediaItemInfo_Value(item, "D_FADEOUTLEN", fade_out_seconds)
        reaper.SetMediaItemInfo_Value(item, "D_FADEOUTLEN_AUTO", fade_out_seconds)
    end
end

function copy_item_properties(from_item, to_item)
    local props = {"D_VOL", "B_MUTE", "B_LOOPSRC", "C_LOCK"}
    for _, prop in ipairs(props) do
        local value = reaper.GetMediaItemInfo_Value(from_item, prop)
        reaper.SetMediaItemInfo_Value(to_item, prop, value)
    end

    local _, item_name = reaper.GetSetMediaItemInfo_String(from_item, "P_NOTES", "", false)
    if item_name and item_name ~= "" then
        reaper.GetSetMediaItemInfo_String(to_item, "P_NOTES", item_name, true)
    end
end

function get_topmost_track()
    if reaper.CountTracks(0) == 0 then
        return nil
    end
    return reaper.GetTrack(0, 0)
end

function apply_clip_to_multitrack(clip, xml_sample_rate, project_sample_rate, cursor_offset)
    local clean_name = clean_clip_name(clip.name)
    local region_start, region_end = find_region_by_name(clean_name)

    if not region_start then
        return false, "Region '" .. clean_name .. "' not found"
    end

    local region_items = get_media_items_in_region(region_start, region_end)
    if #region_items == 0 then
        return false, "No items in region '" .. clean_name .. "'"
    end

    -- Convert XML sample positions to Reaper project time
    -- XML uses samples at its sample rate, Reaper uses seconds
    local source_start_in_region = samples_to_seconds(clip.source_in, xml_sample_rate)
    local source_end_in_region = samples_to_seconds(clip.source_out, xml_sample_rate)
    local dest_position_in_xml = samples_to_seconds(clip.dest_in, xml_sample_rate)

    -- Apply cursor offset to destination position
    local dest_position = cursor_offset + dest_position_in_xml

    -- Calculate actual positions in the region
    local region_source_start = region_start + source_start_in_region
    local region_source_end = region_start + source_end_in_region

    local created_count = 0
    local topmost_track = get_topmost_track()

    -- For each multitrack item in the region, create a corresponding item at destination
    for _, data in ipairs(region_items) do
        local take = reaper.GetActiveTake(data.item)
        if take then
            local item_end = data.pos + data.length

            -- Check if this region item overlaps with our desired slice
            if item_end > region_source_start and data.pos < region_source_end then
                local slice_start = math.max(data.pos, region_source_start)
                local slice_end = math.min(item_end, region_source_end)

                if slice_start < slice_end then
                    local slice_length = slice_end - slice_start
                    local offset_in_dest = slice_start - region_source_start

                    -- Create new item at destination position
                    local new_item = reaper.AddMediaItemToTrack(data.track)
                    reaper.SetMediaItemInfo_Value(new_item, "D_POSITION", dest_position + offset_in_dest)
                    reaper.SetMediaItemInfo_Value(new_item, "D_LENGTH", slice_length)

                    -- Create take with same source
                    local new_take = reaper.AddTakeToMediaItem(new_item)
                    reaper.SetMediaItemTake_Source(new_take, reaper.GetMediaItemTake_Source(take))

                    -- Set source offset
                    local orig_offset = reaper.GetMediaItemTakeInfo_Value(take, "D_STARTOFFS")
                    reaper.SetMediaItemTakeInfo_Value(new_take, "D_STARTOFFS", orig_offset + slice_start - data.pos)

                    -- Copy take name (or use region name for topmost track)
                    local _, original_take_name = reaper.GetSetMediaItemTakeInfo_String(take, "P_NAME", "", false)
                    if topmost_track and data.track == topmost_track then
                        -- For topmost track, name items with the region name
                        reaper.GetSetMediaItemTakeInfo_String(new_take, "P_NAME", clean_name, true)
                    elseif original_take_name and original_take_name ~= "" then
                        reaper.GetSetMediaItemTakeInfo_String(new_take, "P_NAME", original_take_name, true)
                    end

                    -- Copy item properties
                    copy_item_properties(data.item, new_item)

                    -- Apply fades (only to first and last items)
                    if offset_in_dest == 0 then
                        -- This is the first item in the clip - apply fade in
                        apply_fades_to_item(new_item, clip.fade_in, 0, xml_sample_rate)
                    end

                    if slice_end >= region_source_end - 0.001 then
                        -- This is the last item in the clip - apply fade out
                        apply_fades_to_item(new_item, 0, clip.fade_out, xml_sample_rate)
                    end

                    created_count = created_count + 1
                end
            end
        end
    end

    return true, created_count .. " items created"
end

function main()
    -- Get XML file path from user if not set
    if xml_file_path == "" then
        local retval, user_path = reaper.GetUserFileNameForRead("", "Select Pyramix XML File", ".xml")
        if not retval or user_path == "" then
            msg("Cancelled by user")
            return
        end
        xml_file_path = user_path
    end

    msg("Reading XML file: " .. xml_file_path)

    -- Parse XML
    local edl_data, err = parse_pyramix_xml(xml_file_path)
    if not edl_data then
        reaper.ShowMessageBox("Error parsing XML: " .. err, "Error", 0)
        return
    end

    msg("XML parsed successfully")
    msg("Sample rate: " .. edl_data.sampling_rate .. " Hz")
    msg("Total clips: " .. #edl_data.clips)
    msg("")

    -- Get Reaper project sample rate
    local project_sample_rate = reaper.GetSetProjectInfo(0, "PROJECT_SRATE", 0, false)
    msg("Reaper project sample rate: " .. project_sample_rate .. " Hz")

    if edl_data.sampling_rate ~= project_sample_rate then
        local response = reaper.ShowMessageBox(
            "Warning: XML sample rate (" .. edl_data.sampling_rate .. " Hz) does not match project sample rate (" .. project_sample_rate .. " Hz).\n\n" ..
            "This may cause timing issues. Continue anyway?",
            "Sample Rate Mismatch",
            4  -- Yes/No
        )
        if response == 7 then  -- No
            msg("Cancelled due to sample rate mismatch")
            return
        end
    end

    -- Get current edit cursor position
    local cursor_position = reaper.GetCursorPosition()
    msg("Edit cursor position: " .. cursor_position .. " seconds")
    msg("Edited multitrack audio will be placed starting at cursor position")
    msg("")

    reaper.Undo_BeginBlock()

    local success_count = 0
    local errors = {}

    for i, clip in ipairs(edl_data.clips) do
        local clean_name = clean_clip_name(clip.name)
        msg("Processing clip " .. i .. "/" .. #edl_data.clips .. ": " .. clean_name)
        msg("  Source: " .. clip.source_in .. " to " .. clip.source_out .. " (samples)")
        msg("  Destination: " .. clip.dest_in .. " (samples) -> " .. (cursor_position + samples_to_seconds(clip.dest_in, edl_data.sampling_rate)) .. " seconds in project")
        msg("  Fade in: " .. clip.fade_in .. " samples, Fade out: " .. clip.fade_out .. " samples")

        local ok, result = apply_clip_to_multitrack(clip, edl_data.sampling_rate, project_sample_rate, cursor_position)
        if ok then
            msg("  ✓ " .. result)
            success_count = success_count + 1
        else
            msg("  ✗ Error: " .. result)
            errors[#errors + 1] = "Clip " .. i .. " (" .. clean_name .. "): " .. result
        end
        msg("")
    end

    reaper.UpdateArrange()
    reaper.Undo_EndBlock("Apply Pyramix XML to Multitrack", -1)

    local result_msg = success_count .. " of " .. #edl_data.clips .. " clips applied successfully"
    if #errors > 0 then
        result_msg = result_msg .. "\n\nErrors:\n• " .. table.concat(errors, "\n• ")
    end

    msg("===================")
    msg("COMPLETE")
    msg(result_msg)
    reaper.ShowMessageBox(result_msg, "Import Complete", 0)
end

-- Entry point
reaper.ClearConsole()
main()
