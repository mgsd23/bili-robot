-- ----------------------------
-- Table structure for msg
-- ----------------------------
DROP TABLE IF EXISTS "public"."msg";
CREATE TABLE "public"."msg" (
  "msg_key" int8 NOT NULL,
  "content" jsonb,
  "data" jsonb,
  "mid" int4
)
;

-- ----------------------------
-- Primary Key structure for table msg
-- ----------------------------
ALTER TABLE "public"."msg" ADD CONSTRAINT "msg_pkey" PRIMARY KEY ("msg_key");

-- ----------------------------
-- Table structure for img
-- ----------------------------
DROP TABLE IF EXISTS "public"."img";
CREATE TABLE "public"."img" (
  "id" varchar(64) COLLATE "pg_catalog"."default" NOT NULL,
  "url" varchar(255) COLLATE "pg_catalog"."default",
  "gene_short_url" varchar(255) COLLATE "pg_catalog"."default",
  "short_url" varchar(64) COLLATE "pg_catalog"."default",
  "width" int4,
  "height" int4,
  "size" int4,
  "tx_content_review" jsonb,
  "image_type" varchar(16) COLLATE "pg_catalog"."default",
  "create_at" timestamp(6) DEFAULT CURRENT_TIMESTAMP
)
;
COMMENT ON COLUMN "public"."img"."id" IS 'SHA1';
COMMENT ON COLUMN "public"."img"."url" IS '图片链接';
COMMENT ON COLUMN "public"."img"."gene_short_url" IS '生成短链的url，因为原始url可能无法直接生成短链';
COMMENT ON COLUMN "public"."img"."short_url" IS '短链接';
COMMENT ON COLUMN "public"."img"."width" IS '宽（像素）';
COMMENT ON COLUMN "public"."img"."height" IS '高（像素）';
COMMENT ON COLUMN "public"."img"."size" IS '文件大小（kB）';
COMMENT ON COLUMN "public"."img"."tx_content_review" IS '腾讯内容审核';
COMMENT ON COLUMN "public"."img"."image_type" IS '图片类型';

-- ----------------------------
-- Primary Key structure for table img
-- ----------------------------
ALTER TABLE "public"."img" ADD CONSTRAINT "img_pkey" PRIMARY KEY ("id");


--
CREATE VIEW "public"."msg_all" AS  SELECT msg.msg_key,
    (msg.data -> 'msg_type'::text)::integer AS msg_type,
    (msg.data -> 'msg_seqno'::text)::integer AS msg_seqno,
    to_timestamp((msg.data -> 'timestamp'::text)::double precision) AS "timestamp",
    (msg.data -> 'msg_status'::text)::integer AS msg_status,
    (msg.data -> 'sender_uid'::text)::integer AS sender_uid,
    (msg.data -> 'sys_cancel'::text)::boolean AS sys_cancel,
    msg.data ->> 'notify_code'::text AS notify_code,
    (msg.data -> 'receiver_id'::text)::integer AS receiver_id,
    (msg.data -> 'receiver_type'::text)::integer AS receiver_type,
    msg.content ->> 'content'::text AS msg_content,
    msg.content ->> 'url'::text AS msg_url,
    msg.content,
    msg.data
   FROM msg
  ORDER BY msg.msg_key DESC;

ALTER TABLE "public"."msg_all" OWNER TO "postgres";


--
CREATE VIEW "public"."msg_del" AS  SELECT t2.msg_key,
    t1.msg_key AS rec_msg_key,
    t1.data -> 'sys_cancel'::text AS sys_cancel,
    t2.msg_type,
    t2.msg_seqno,
    t2."timestamp",
    t2.msg_status,
    t2.sender_uid,
    t2.notify_code,
    t2.receiver_id,
    t2.receiver_type,
    t2.msg_content,
    t2.msg_url,
    t2.content,
    t2.data
   FROM msg_all t2
     LEFT JOIN msg t1 ON t1.content::text = t2.msg_key::text
  WHERE t1.msg_key IS NOT NULL
  ORDER BY t2.msg_key DESC;

ALTER TABLE "public"."msg_del" OWNER TO "postgres";
