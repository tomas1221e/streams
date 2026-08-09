# Onside Restreamer fixes

This build fixes the custom additions without redesigning the Restreamer UI:

- Color filter labels now render as readable names instead of Lingui message IDs.
- Logo upload is wired into Source editing and Publication Add/Edit forms.
- Logo upload failures are reported instead of silently returning a path.
- Logo URL construction is normalized against the connected Restreamer Core address.
- Logo overlay FFmpeg filter graph braces/order were repaired.
- Existing Onside branding is preserved.

The custom video filters require video transcoding. They cannot be applied while the video codec is set to Passthrough/Copy.
