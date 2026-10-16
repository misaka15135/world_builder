Shader "WorldBuilder/BridgeDepthBias"
{
    Properties
    {
        _Color ("Color", Color) = (1,1,1,1)
        _Glossiness ("Smoothness", Range(0,1)) = 0.12
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" }
        LOD 200
        // The embedded bank and bridge top intentionally meet at equal height.
        // Resolve their coplanar appearance without moving source/collider data.
        Offset -1, -1
        CGPROGRAM
        #pragma surface surf Standard fullforwardshadows
        #pragma target 3.0
        struct Input { float3 worldPos; };
        fixed4 _Color;
        half _Glossiness;
        void surf(Input IN, inout SurfaceOutputStandard o)
        {
            o.Albedo=_Color.rgb; o.Metallic=0; o.Smoothness=_Glossiness; o.Alpha=1;
        }
        ENDCG
    }
    FallBack "Standard"
}
