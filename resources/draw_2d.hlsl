// **** RESPONSIVE UI SHADER ****
// Contributors: SinsOfSeven
// Ispired by VV_Mod_Maker

Texture1D<float4> IniParams : register(t120);

#define SIZE IniParams[87].xy
#define OFFSET IniParams[87].zw

struct vs2ps {
	float4 pos : SV_Position0;
	float2 uv : TEXCOORD1;
};

#ifdef VERTEX_SHADER
void main(
		out vs2ps output,
		uint vertex : SV_VertexID)
{
	float2 BaseCoord,Offset;
	Offset.x = OFFSET.x*2-1;
	Offset.y = (1-OFFSET.y)*2-1;
	BaseCoord.xy = float2((2*SIZE.x),(2*(-SIZE.y)));
	// Not using vertex buffers so manufacture our own coordinates.
	switch(vertex) {
		case 0:
			output.pos.xy = float2(BaseCoord.x+Offset.x, BaseCoord.y+Offset.y);
			output.uv = float2(1,0);
			break;
		case 1:
			output.pos.xy = float2(BaseCoord.x+Offset.x, 0+Offset.y);
			output.uv = float2(1,1);
			break;
		case 2:
			output.pos.xy = float2(0+Offset.x, BaseCoord.y+Offset.y);
			output.uv = float2(0,0);
			break;
		case 3:
			output.pos.xy = float2(0+Offset.x, 0+Offset.y);
			output.uv = float2(0,1);
			break;
		default:
			output.pos.xy = 0;
			output.uv = float2(0,0);
			break;
	};
	output.pos.zw = float2(0, 1);
}
#endif

#ifdef PIXEL_SHADER
Texture2D<float4> tex : register(t100);

// Generate a stable neon palette without requiring extra runtime parameters.
float3 palette(float t)
{
	return 0.55 + 0.45 * cos(6.2831853 * (t + float3(0.00, 0.17, 0.34)));
}

// Used to preserve readable contrast when polishing UI textures.
float luminance(float3 color)
{
	return dot(color, float3(0.2126, 0.7152, 0.0722));
}

// Border strips are extremely thin in one axis, while panels and buttons are not.
// This heuristic lets the shader style borders more aggressively without extra ini tags.
float get_border_mask(float2 safe_size)
{
	float aspect_ratio = min(safe_size.x, safe_size.y) / max(safe_size.x, safe_size.y);
	return saturate((0.08 - aspect_ratio) / 0.08);
}

// Build a static neon treatment that runs along the long edge of a border strip.
float3 apply_neon_border(float3 base_rgb, float2 uv, float2 safe_size)
{
	float is_horizontal = step(safe_size.y, safe_size.x);
	float long_axis = lerp(uv.y, uv.x, is_horizontal);
	float thin_axis_dist = lerp(abs(uv.x * 2 - 1), abs(uv.y * 2 - 1), is_horizontal);

	float3 neon_ramp = palette(long_axis * 0.9 + 0.08);
	float edge_glow = pow(saturate(1.0 - thin_axis_dist), 2.4);

	float3 neon_border = lerp(base_rgb, neon_ramp, 0.82);
	neon_border += neon_ramp * edge_glow * 0.28;
	return saturate(neon_border);
}

// Give regular UI textures a little more depth so the panel no longer looks flat.
// This stays subtle to avoid destroying icons and text readability.
float3 polish_ui_surface(float3 base_rgb, float base_alpha, float2 uv)
{
	float diagonal_band = saturate(1.0 - abs((uv.x + uv.y) - 1.0) * 1.35);
	float corner_vignette = saturate(16.0 * uv.x * uv.y * (1.0 - uv.x) * (1.0 - uv.y));
	float3 accent_ramp = palette(uv.x * 0.32 + uv.y * 0.18 + 0.21);
	float alpha_mask = saturate(base_alpha * 1.25);
	float luma = luminance(base_rgb);

	float3 polished = base_rgb;
	polished *= lerp(0.95, 1.06, sqrt(corner_vignette));
	polished += accent_ramp * diagonal_band * 0.08 * alpha_mask;
	polished = lerp(float3(luma, luma, luma), polished, 1.08);
	return saturate((polished - 0.5) * 1.08 + 0.5);
}

void main(vs2ps input, out float4 result : SV_Target0)
{
	float2 dims;
	tex.GetDimensions(dims.x, dims.y);
	if (!dims.x || !dims.y) discard;
	input.uv.y = 1 - input.uv.y;

	float4 base = tex.Load(int3(input.uv.xy * dims.xy, 0));
	float2 uv = saturate(input.uv);
	float2 safe_size = max(SIZE, 0.0001.xx);
	float border_mask = get_border_mask(safe_size);
	float alpha_mask = saturate(base.a * 1.25);
	float3 polished = polish_ui_surface(base.rgb, base.a, uv);
	float3 neon_border = apply_neon_border(base.rgb, uv, safe_size);
	float3 final_rgb = lerp(polished, neon_border, border_mask * alpha_mask);
	result = float4(final_rgb, base.a);
}
#endif
