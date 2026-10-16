using System;
using System.IO;
using UnityEngine;

/// <summary>Frame-stepped collision validation, uncapped for the 512m test batch.</summary>
public sealed class WorldBuilderCityWalk : MonoBehaviour
{
    [Serializable] public sealed class Result
    {
        public string status="in_progress",method="Unity_PlayMode_CharacterController_continuous_city_routes",error,unity_version;
        public int expected_routes,completed_routes,grounded_frames,frames;
        public string[] completed_rooms;
    }
    public WorldBuilder042Walk.Path[] paths;
    public string resultPath;
    public bool terrainGravity;
    CharacterController controller;
    Result result;
    int routeIndex,pointIndex,stuck;
    float best=float.MaxValue;
    float downStep=.01f;
    void Start()
    {
        QualitySettings.vSyncCount=0;Application.targetFrameRate=-1;
        controller=GetComponent<CharacterController>();
        result=new Result {expected_routes=paths.Length,completed_rooms=new string[paths.Length],unity_version=Application.unityVersion};
        if(terrainGravity)result.method+="_terrain_gravity_v1";
        BeginRoute();
    }
    void BeginRoute()
    {
        controller.enabled=false;transform.position=paths[routeIndex].points[0]+Vector3.up*.025f;controller.enabled=true;
        pointIndex=1;stuck=0;best=float.MaxValue;downStep=.01f;
    }
    void Update()
    {
        if(result.status!="in_progress")return;
        result.frames++;if(result.frames>250000){Finish(false,"frame_budget");return;}
        Vector3 target=paths[routeIndex].points[pointIndex];Vector3 delta=target-transform.position;delta.y=0;
        float distance=delta.magnitude;bool critical=Array.IndexOf(paths[routeIndex].critical_indices,pointIndex)>=0;
        if(distance<.06f&&Mathf.Abs(transform.position.y-target.y)<(critical?.08f:.23f))
        {
            pointIndex++;stuck=0;best=float.MaxValue;
            if(pointIndex==paths[routeIndex].points.Length)
            {
                result.completed_rooms[routeIndex]=paths[routeIndex].room;result.completed_routes++;routeIndex++;
                if(routeIndex==paths.Length){Finish(true,null);return;}
                BeginRoute();
            }
            return;
        }
        if(distance<best-.003f){best=distance;stuck=0;}else stuck++;
        if(stuck>600){Finish(false,paths[routeIndex].room+" blocked at point "+pointIndex+" position "+transform.position+" target "+target);return;}
        Vector3 movement=delta.normalized*Mathf.Min(.04f,distance);
        if(terrainGravity)
        {
            // Fixed 0.01s simulated step: held-ground speed 1m/s and falling
            // acceleration 20m/s², not a per-frame constant falling speed.
            // Actual cross-slope safety is enforced in source route planning;
            // the flat-city mode and all checkpoint tolerances stay unchanged.
            downStep=controller.isGrounded?.01f:Mathf.Min(.3f,downStep+.002f);
            movement.y=-downStep;
        }
        else movement.y=-.045f;
        controller.Move(movement);if(controller.isGrounded)result.grounded_frames++;
    }
    void Finish(bool pass,string error)
    {
        result.status=pass?"pass":"fail";result.error=error;
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(resultPath)));File.WriteAllText(resultPath,JsonUtility.ToJson(result,true));
#if UNITY_EDITOR
        if(Application.isBatchMode)UnityEditor.EditorApplication.Exit(pass?0:1);else UnityEditor.EditorApplication.isPlaying=false;
#endif
    }
}
