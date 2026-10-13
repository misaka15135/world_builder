using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Security.Cryptography;
using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine.Rendering;

public static class WorldBuilder042Builder
{
    [Serializable] sealed class Piece { public string name,source_id,group,component; public bool solid; public int material; }
    [Serializable] sealed class Manifest { public string source_id,source_revision_id,glb_sha256; public int piece_count; public Piece[] pieces; }
    [Serializable] sealed class Pbr { public float[] baseColorFactor; }
    [Serializable] sealed class GMat { public Pbr pbrMetallicRoughness; }
    [Serializable] sealed class GDoc { public GMat[] materials; }
    [Serializable] sealed class PieceBounds { public string name; public Vector3 min,max; }
    [Serializable] sealed class BoundsSet { public PieceBounds[] pieces; }
    [Serializable] sealed class Report
    {
        public string status="in_progress",target_load="not_run",collision="not_run",error,source_revision_id,glb_sha256,unity_version;
        public int expected_pieces,mapped_pieces,mesh_colliders,bounds_checked;
    }
    static string CaseName=>Environment.GetEnvironmentVariable("WB042_CASE")??"API";
    static string Base=>"Assets/Generated/"+CaseName+"/";
    static string Evidence=>Environment.GetEnvironmentVariable("WB042_EVIDENCE")??Path.GetFullPath("Evidence/"+CaseName);
    static string ScenePath=>"Assets/Generated/"+CaseName+"/Arcane"+CaseName+".unity";

    [MenuItem("World Builder/042/Build API Scene")]
    public static void Build()
    {
        Directory.CreateDirectory(Evidence);
        var report=new Report { unity_version=Application.unityVersion };
        try
        {
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            var manifest=JsonUtility.FromJson<Manifest>(File.ReadAllText(Base+"manifest.json"));
            report.expected_pieces=manifest.piece_count;report.source_revision_id=manifest.source_revision_id;report.glb_sha256=manifest.glb_sha256;
            var prefab=AssetDatabase.LoadAssetAtPath<GameObject>(Base+"scene.glb");
            if(prefab==null)throw new Exception("glTFast did not import GLB");
            var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
            var root=UnityEngine.Object.Instantiate(prefab);root.name=manifest.source_id;
            byte[] glb=File.ReadAllBytes(Base+"scene.glb");
            using(var sha=SHA256.Create())
                if("sha256:"+BitConverter.ToString(sha.ComputeHash(glb)).Replace("-","").ToLowerInvariant()!=manifest.glb_sha256)
                    throw new Exception("GLB hash differs from manifest");
            var boundsSet=JsonUtility.FromJson<BoundsSet>(File.ReadAllText(Base+"unity_bounds.json"));
            int jsonLength=BitConverter.ToInt32(glb,12);
            var doc=JsonUtility.FromJson<GDoc>(Encoding.UTF8.GetString(glb,20,jsonLength).TrimEnd(' ','\0'));
            var materials=new Material[doc.materials.Length];
            for(int i=0;i<materials.Length;i++)
            {
                string path=Base+"view_material_"+i+".mat";
                var material=AssetDatabase.LoadAssetAtPath<Material>(path);
                if(material==null){ material=new Material(Shader.Find("Standard"));AssetDatabase.CreateAsset(material,path); }
                var c=doc.materials[i].pbrMetallicRoughness.baseColorFactor;
                material.color=new Color(c[0],c[1],c[2],c[3]);material.SetFloat("_Glossiness",.15f);
                if(c[3]<.99f)
                {
                    material.SetFloat("_Mode",3);material.SetInt("_SrcBlend",(int)BlendMode.SrcAlpha);
                    material.SetInt("_DstBlend",(int)BlendMode.OneMinusSrcAlpha);material.SetInt("_ZWrite",0);
                    material.EnableKeyword("_ALPHAPREMULTIPLY_ON");material.renderQueue=3000;
                }
                materials[i]=material;
            }
            foreach(var piece in manifest.pieces)
            {
                Transform node=root.GetComponentsInChildren<Transform>().FirstOrDefault(t=>t.name==piece.name);
                if(node==null)throw new Exception("Missing node "+piece.name);
                var mesh=node.GetComponentInChildren<MeshFilter>();
                if(mesh==null||mesh.sharedMesh==null)throw new Exception("Missing mesh "+piece.name);
                var renderer=mesh.GetComponent<MeshRenderer>();renderer.sharedMaterial=materials[piece.material];
                var expected=boundsSet.pieces.First(p=>p.name==piece.name);
                if(Vector3.Distance(renderer.bounds.min,expected.min)>.005f||Vector3.Distance(renderer.bounds.max,expected.max)>.005f)
                    throw new Exception("Unity/WIR bounds differ "+piece.name+" actual "+renderer.bounds);
                report.bounds_checked++;
                if(piece.solid){mesh.gameObject.AddComponent<MeshCollider>().sharedMesh=mesh.sharedMesh;report.mesh_colliders++;}
                report.mapped_pieces++;
            }
            RenderSettings.ambientMode=AmbientMode.Flat;RenderSettings.ambientLight=new Color(.72f,.72f,.70f);
            var light=new GameObject("Sun").AddComponent<Light>();light.type=LightType.Directional;light.intensity=1.15f;
            light.shadows=LightShadows.Soft;light.transform.rotation=Quaternion.Euler(45,-35,0);
            QualitySettings.shadowDistance=150;
            var camera=new GameObject("Overview Camera").AddComponent<Camera>();camera.tag="MainCamera";
            camera.clearFlags=CameraClearFlags.SolidColor;camera.backgroundColor=new Color(.76f,.84f,.91f);
            camera.transform.position=new Vector3(82,67,-32);camera.transform.LookAt(new Vector3(32,2,30));
            camera.fieldOfView=47;camera.farClipPlane=300;camera.gameObject.AddComponent<WorldBuilder042Explorer>();
            Physics.SyncTransforms();
            EditorSceneManager.SaveScene(scene,ScenePath);AssetDatabase.SaveAssets();
            Render(camera,"overview",new Vector3(82,67,-32),new Vector3(32,2,30),47);
            Render(camera,"street",new Vector3(32,5,25),new Vector3(28,4,44),65);
            Render(camera,"detail",new Vector3(0,6,25),new Vector3(11,4,36),58);
            report.status="pass";report.target_load="pass";report.collision="pass";
        }
        catch(Exception e){report.status="fail";report.error=e.ToString();Debug.LogException(e);}
        File.WriteAllText(Path.Combine(Evidence,"target_validation.json"),JsonUtility.ToJson(report,true));
        if(report.status!="pass")throw new Exception(report.error);
    }

    static void Render(Camera camera,string name,Vector3 position,Vector3 target,float fov)
    {
        camera.transform.position=position;camera.transform.LookAt(target);camera.fieldOfView=fov;
        var texture=new RenderTexture(1280,900,24);camera.targetTexture=texture;camera.Render();
        var old=RenderTexture.active;RenderTexture.active=texture;
        var image=new Texture2D(1280,900,TextureFormat.RGB24,false);image.ReadPixels(new Rect(0,0,1280,900),0,0);image.Apply();
        File.WriteAllBytes(Path.Combine(Evidence,name+".png"),image.EncodeToPNG());
        RenderTexture.active=old;camera.targetTexture=null;texture.Release();UnityEngine.Object.DestroyImmediate(image);
    }

    public static void Reopen()
    {
        EditorSceneManager.OpenScene(ScenePath);
        var manifest=JsonUtility.FromJson<Manifest>(File.ReadAllText(Base+"manifest.json"));
        var root=GameObject.Find(manifest.source_id);
        var boundsSet=JsonUtility.FromJson<BoundsSet>(File.ReadAllText(Base+"unity_bounds.json"));
        var report=new Report { unity_version=Application.unityVersion,expected_pieces=manifest.piece_count,
                                 source_revision_id=manifest.source_revision_id,glb_sha256=manifest.glb_sha256 };
        if(root==null)throw new Exception("Saved source root missing");
        foreach(var p in manifest.pieces)
        {
            var node=root.GetComponentsInChildren<Transform>().First(t=>t.name==p.name);
            if(node.GetComponentInChildren<MeshFilter>()==null)throw new Exception("Saved mesh missing");
            if(p.solid&&node.GetComponentInChildren<MeshCollider>()==null)throw new Exception("Saved collider missing");
            var expected=boundsSet.pieces.First(b=>b.name==p.name);
            var renderer=node.GetComponentInChildren<MeshRenderer>();
            if(Vector3.Distance(renderer.bounds.min,expected.min)>.005f||Vector3.Distance(renderer.bounds.max,expected.max)>.005f)
                throw new Exception("Saved bounds differ "+p.name);
            report.bounds_checked++;
            report.mapped_pieces++;if(p.solid)report.mesh_colliders++;
        }
        report.status="pass";report.target_load="pass";report.collision="pass";
        Directory.CreateDirectory(Evidence);
        File.WriteAllText(Path.Combine(Evidence,"target_reopen.json"),JsonUtility.ToJson(report,true));
    }

    public static void VerifyWalk()
    {
        Reopen();
        // Python expands nested source cells into Unity Vector3 points for JsonUtility.
        var paths=JsonUtility.FromJson<PathSet>(File.ReadAllText(Base+"unity_paths.json"));
        var body=new GameObject("Automated Walking Validator");
        var controller=body.AddComponent<CharacterController>();controller.height=1.8f;controller.radius=.28f;
        controller.center=new Vector3(0,.9f,0);controller.skinWidth=.015f;controller.stepOffset=.3f;controller.slopeLimit=50;
        var walker=body.AddComponent<WorldBuilder042Walk>();walker.paths=paths.paths;
        walker.resultPath=Path.Combine(Evidence,"walk_validation.json");
        EditorSceneManager.SaveScene(body.scene,Base+"ArcaneWalkValidation.unity");
        EditorApplication.isPlaying=true;
    }
    [Serializable] sealed class PathSet { public WorldBuilder042Walk.Path[] paths; }

    [MenuItem("World Builder/042/Open Delivered API Scene")]
    public static void OpenAPI()
    {
        EditorSceneManager.OpenScene("Assets/Generated/API/ArcaneAPI.unity",OpenSceneMode.Single);
    }

    public static void VerifyBothSaved()
    {
        Environment.SetEnvironmentVariable("WB042_CASE","Baseline");
        Environment.SetEnvironmentVariable("WB042_EVIDENCE",Path.GetFullPath("../../../artifacts/style042/baseline-v3/unity-evidence"));
        Reopen();
        Environment.SetEnvironmentVariable("WB042_CASE","API");
        Environment.SetEnvironmentVariable("WB042_EVIDENCE",Path.GetFullPath("../../../artifacts/style042/arcane-v3/unity-evidence"));
        Reopen();
    }

    public static void RenderBothSaved()
    {
        foreach(string name in new[]{"Baseline","API"})
        {
            Environment.SetEnvironmentVariable("WB042_CASE",name);
            string folder=name=="API"?"arcane-v3":"baseline-v3";
            Environment.SetEnvironmentVariable("WB042_EVIDENCE",Path.GetFullPath("../../../artifacts/style042/"+folder+"/unity-evidence"));
            Reopen();
            var camera=Camera.main;
            Render(camera,"overview",new Vector3(82,67,-32),new Vector3(32,2,30),47);
            Render(camera,"street",new Vector3(32,5,25),new Vector3(28,4,44),65);
            Render(camera,"detail",new Vector3(0,6,25),new Vector3(11,4,36),58);
        }
    }
}
